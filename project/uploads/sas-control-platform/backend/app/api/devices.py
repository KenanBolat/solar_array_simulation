from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.drivers import get_driver_registry
from app.models import Device, Measurement
from app.schemas.common import (
    CommandIn,
    CommandResultOut,
    CommandTemplateOut,
    DeviceOut,
    DeviceStateOut,
    MeasurementOut,
    OutputIn,
)
from app.security import Principal, require
from app.services.command_service import HazardousActionUnconfirmed, run_command

router = APIRouter(prefix="/api/devices", tags=["devices"])


async def _get_device(session: AsyncSession, device_id: uuid.UUID) -> Device:
    d = (await session.execute(select(Device).where(Device.id == device_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(404, "device not found")
    return d


@router.get("", response_model=list[DeviceOut])
async def list_devices(rack_id: uuid.UUID | None = None,
                       session: AsyncSession = Depends(get_session),
                       _=Depends(require("view"))):
    stmt = select(Device)
    if rack_id:
        stmt = stmt.where(Device.rack_id == rack_id)
    return (await session.execute(stmt.order_by(Device.name))).scalars().all()


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                     _=Depends(require("view"))):
    return await _get_device(session, device_id)


@router.get("/{device_id}/state", response_model=DeviceStateOut)
async def device_state(device_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                       _=Depends(require("view"))):
    d = await _get_device(session, device_id)
    p = d.connection_profile
    driver = get_driver_registry().get_or_create(
        str(d.id), resource=p.visa_resource, driver_kind=p.driver_kind,
        fault_profile=p.fault_profile)
    try:
        if not getattr(driver, "_connected", False):
            await driver.connect()
        s = await driver.read_state()
    except Exception as exc:
        raise HTTPException(502, f"device read failed: {exc}") from exc
    return DeviceStateOut(
        device_id=d.id, connected=s.connected, device_state=s.device_state.value,
        output_enabled=s.output_enabled, remote_mode=s.remote_mode, voltage_v=s.voltage_v,
        current_a=s.current_a, power_w=s.power_w, device_mode=s.device_mode,
        alarm_state=s.alarm_state, firmware=s.firmware, last_comm_utc=s.last_comm_utc,
        comm_health=s.comm_health, simulation=not settings.hardware_enabled)


@router.get("/{device_id}/capabilities", response_model=list[CommandTemplateOut])
async def device_capabilities(device_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                              _=Depends(require("view"))):
    d = await _get_device(session, device_id)
    p = d.connection_profile
    driver = get_driver_registry().get_or_create(
        str(d.id), resource=p.visa_resource, driver_kind=p.driver_kind,
        fault_profile=p.fault_profile)
    caps = driver.get_capabilities()
    return [CommandTemplateOut(
        id=t.id, title=t.title, description=t.description, hazardous=t.hazardous,
        requires_confirmation=t.requires_confirmation, idempotent=t.idempotent,
        verified=t.verified, parameters=t.parameters) for t in caps.command_templates]


@router.get("/{device_id}/measurements", response_model=list[MeasurementOut])
async def device_measurements(
    device_id: uuid.UUID,
    window: str = Query("5m", pattern="^(5m|30m|1h|24h|custom)$"),
    start: datetime | None = None, end: datetime | None = None,
    limit: int = Query(2000, le=20000),
    session: AsyncSession = Depends(get_session), _=Depends(require("view"))):
    now = datetime.now(UTC)
    deltas = {"5m": timedelta(minutes=5), "30m": timedelta(minutes=30),
              "1h": timedelta(hours=1), "24h": timedelta(hours=24)}
    if window == "custom":
        t0, t1 = start or now - timedelta(minutes=5), end or now
    else:
        t0, t1 = now - deltas[window], now
    stmt = (select(Measurement)
            .where(Measurement.device_id == device_id,
                   Measurement.timestamp_utc >= t0, Measurement.timestamp_utc <= t1)
            .order_by(Measurement.timestamp_utc).limit(limit))
    return (await session.execute(stmt)).scalars().all()


@router.get("/{device_id}/measurements.csv")
async def measurements_csv(device_id: uuid.UUID, window: str = "1h",
                           session: AsyncSession = Depends(get_session),
                           _=Depends(require("view"))):
    rows = await device_measurements(device_id, window=window, session=session, _=_)  # type: ignore
    lines = ["timestamp_utc,voltage_v,current_a,power_w,output_enabled,device_state,quality_flag"]
    for r in rows:
        lines.append(f"{r.timestamp_utc.isoformat()},{r.voltage_v},{r.current_a},"
                     f"{r.power_w},{r.output_enabled},{r.device_state},{r.quality_flag}")
    return Response("\n".join(lines), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=measurements_{device_id}.csv"})


@router.post("/{device_id}/commands", response_model=CommandResultOut)
async def post_command(device_id: uuid.UUID, body: CommandIn,
                       principal: Principal = Depends(require("control_output")),
                       session: AsyncSession = Depends(get_session)):
    d = await _get_device(session, device_id)
    try:
        row = await run_command(session, d, body.template_id, body.params,
                                actor=principal.username, confirmed=body.confirmed,
                                correlation_id=body.correlation_id)
    except HazardousActionUnconfirmed:
        raise HTTPException(428, "confirmation required for hazardous command") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await session.commit()
    return row


@router.post("/{device_id}/output", response_model=CommandResultOut)
async def post_output(device_id: uuid.UUID, body: OutputIn,
                      principal: Principal = Depends(require("control_output")),
                      session: AsyncSession = Depends(get_session)):
    d = await _get_device(session, device_id)
    tid = "output_on" if body.enabled else "output_off"
    try:
        row = await run_command(session, d, tid, {}, actor=principal.username,
                                confirmed=body.confirmed)
    except HazardousActionUnconfirmed:
        raise HTTPException(428, "confirmation required to change output state") from None
    await session.commit()
    return row


@router.post("/{device_id}/safe-shutdown", response_model=CommandResultOut)
async def post_safe_shutdown(device_id: uuid.UUID,
                             principal: Principal = Depends(require("control_output")),
                             session: AsyncSession = Depends(get_session)):
    d = await _get_device(session, device_id)
    row = await run_command(session, d, "safe_shutdown", {}, actor=principal.username,
                            confirmed=True)
    await session.commit()
    return row
