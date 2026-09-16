"""Execute a validated command end-to-end:
queue -> driver -> readback -> persist request/result -> append audit -> metrics -> publish.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.drivers import get_driver_registry
from app.drivers.base import CommandResult, CommandStatus
from app.drivers.templates import TEMPLATES_BY_ID
from app.logging import get_logger
from app.metrics import command_latency, commands_total, failed_commands_total
from app.models import CommandAuditLog, CommandRequest, CommandResultRow, Device
from app.services.command_queue import get_queue_manager
from app.services.eventbus import get_event_bus

log = get_logger("command")


class HazardousActionUnconfirmed(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def run_command(
    session: AsyncSession, device: Device, template_id: str,
    params: dict, actor: str, *, confirmed: bool = False,
    scenario_run_id: uuid.UUID | None = None, correlation_id: str | None = None,
) -> CommandResultRow:
    template = TEMPLATES_BY_ID.get(template_id)
    if template is None:
        raise ValueError(f"unknown template '{template_id}'")
    if template.requires_confirmation and not confirmed:
        raise HazardousActionUnconfirmed(template_id)

    correlation_id = correlation_id or uuid.uuid4().hex[:16]
    profile = device.connection_profile
    driver = get_driver_registry().get_or_create(
        str(device.id), resource=profile.visa_resource,
        driver_kind=profile.driver_kind, fault_profile=profile.fault_profile)

    req = CommandRequest(
        device_id=device.id, template_id=template_id, params=params, status="queued",
        requested_by=actor, scenario_run_id=scenario_run_id,
        correlation_id=correlation_id, confirmed=confirmed)
    session.add(req)
    await session.flush()

    # ensure connection (idempotent, safe to retry)
    queue = get_queue_manager().for_device(str(device.id))
    try:
        await queue.submit(driver.connect)
    except Exception as exc:  # connect failures -> rejected
        log.warning("connect failed", extra={"extra_fields": {"device": str(device.id), "err": str(exc)}})

    req.status = "running"
    await session.flush()

    try:
        result: CommandResult = await queue.submit(
            lambda: driver.execute_validated_command(template, params))
    except TimeoutError:
        now = _utcnow()
        result = CommandResult(CommandStatus.TIMED_OUT, None, None, False,
                               "command timed out", now, now)
    except Exception as exc:
        now = _utcnow()
        result = CommandResult(CommandStatus.FAILED, None, None, False, str(exc), now, now)

    latency = (result.finished_utc - result.started_utc).total_seconds()
    row = CommandResultRow(
        request_id=req.id, status=result.status.value, scpi_sent=result.scpi_sent,
        scpi_response=result.scpi_response, readback_verified=result.readback_verified,
        message=result.message, started_utc=result.started_utc,
        finished_utc=result.finished_utc, latency_ms=int(latency * 1000))
    session.add(row)
    req.status = result.status.value

    # append-only audit
    session.add(CommandAuditLog(
        ts_utc=_utcnow(), actor=actor, action=f"command:{template_id}",
        device_id=device.id, template_id=template_id, correlation_id=correlation_id,
        scenario_run_id=scenario_run_id, outcome=result.status.value,
        detail={"params": params, "readback": result.readback_verified,
                "message": result.message}))
    await session.flush()

    # metrics
    command_latency.labels(template_id, profile.driver_kind).observe(latency)
    commands_total.labels(template_id, result.status.value).inc()
    if result.status in (CommandStatus.FAILED, CommandStatus.REJECTED, CommandStatus.TIMED_OUT):
        failed_commands_total.labels(template_id).inc()

    # publish status to SSE
    await get_event_bus().publish("command_status", {
        "device_id": str(device.id), "template_id": template_id,
        "status": result.status.value, "correlation_id": correlation_id,
        "actor": actor, "ts": _utcnow().isoformat(),
    })
    return row
