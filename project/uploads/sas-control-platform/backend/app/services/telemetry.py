"""Telemetry sampler: periodically reads every device via its driver,
persists a measurement row, raises/clears alarms, updates gauges, and
publishes live updates over the event bus. Runs in the worker process,
and a lightweight copy can run in-process for the API dev server."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.drivers import get_driver_registry
from app.drivers.base import DeviceState
from app.logging import get_logger
from app.metrics import (
    active_alarms,
    active_outputs,
    device_offline,
    device_online,
    measurements_written,
)
from app.models import Alarm, Device, Measurement
from app.services.eventbus import get_event_bus

log = get_logger("telemetry")


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def sample_once() -> None:
    bus = get_event_bus()
    async with SessionLocal() as session:
        devices = (await session.execute(select(Device))).scalars().all()
        online = offline = outputs = alarms = 0
        for d in devices:
            p = d.connection_profile
            driver = get_driver_registry().get_or_create(
                str(d.id), resource=p.visa_resource, driver_kind=p.driver_kind,
                fault_profile=p.fault_profile)
            try:
                if driver.get_capabilities() and not getattr(driver, "_connected", True):
                    await driver.connect()
                m = await driver.read_measurements()
            except Exception as exc:
                offline += 1
                log.debug("read failed", extra={"extra_fields": {"device": str(d.id), "err": str(exc)}})
                continue

            if m.device_state == DeviceState.OFFLINE:
                offline += 1
            else:
                online += 1
            if m.output_enabled:
                outputs += 1

            row = Measurement(
                timestamp_utc=m.timestamp_utc, device_id=d.id, rack_id=d.rack_id,
                mainframe_id=d.mainframe_id, module_id=d.module_id, channel_id=d.channel_id,
                voltage_v=m.voltage_v, current_a=m.current_a, power_w=m.power_w,
                output_enabled=m.output_enabled, device_state=m.device_state.value,
                alarm_state=m.alarm_state, quality_flag=m.quality_flag,
                source_type=m.source_type)
            session.add(row)
            measurements_written.inc()

            # cache last state on the device
            d.last_state = {
                "voltage_v": m.voltage_v, "current_a": m.current_a, "power_w": m.power_w,
                "output_enabled": m.output_enabled, "device_state": m.device_state.value,
                "alarm_state": m.alarm_state, "ts": m.timestamp_utc.isoformat(),
            }

            # alarm lifecycle
            existing = (await session.execute(
                select(Alarm).where(Alarm.device_id == d.id, Alarm.cleared_utc.is_(None))
            )).scalars().all()
            open_codes = {a.code for a in existing}
            if m.alarm_state and m.alarm_state not in open_codes:
                sev = "alarm" if m.device_state == DeviceState.ALARM else "warning"
                session.add(Alarm(device_id=d.id, ts_utc=_utcnow(), severity=sev,
                                  code=m.alarm_state, message=f"{m.alarm_state} on {d.name}"))
                await bus.publish("alarms", {"device_id": str(d.id), "code": m.alarm_state,
                                             "severity": sev, "ts": _utcnow().isoformat()})
            for a in existing:
                if not m.alarm_state:
                    a.cleared_utc = _utcnow()
            alarms += len([a for a in existing if a.cleared_utc is None]) + (
                1 if (m.alarm_state and m.alarm_state not in open_codes) else 0)

            await bus.publish("measurements", {
                "device_id": str(d.id), "voltage_v": m.voltage_v, "current_a": m.current_a,
                "power_w": m.power_w, "output_enabled": m.output_enabled,
                "device_state": m.device_state.value, "ts": m.timestamp_utc.isoformat()})
            await bus.publish("device_state", {
                "device_id": str(d.id), "device_state": m.device_state.value,
                "output_enabled": m.output_enabled, "alarm_state": m.alarm_state})

        device_online.set(online)
        device_offline.set(offline)
        active_outputs.set(outputs)
        active_alarms.set(alarms)
        await session.commit()


async def telemetry_loop(stop_event: asyncio.Event | None = None) -> None:
    log.info("telemetry loop starting (SIMULATION MODE)" if not settings.hardware_enabled
             else "telemetry loop starting (HARDWARE ENABLED)")
    while stop_event is None or not stop_event.is_set():
        try:
            await sample_once()
        except Exception as exc:  # never let the loop die
            log.exception("telemetry sample failed: %s", exc)
        await asyncio.sleep(settings.telemetry_interval_seconds)
