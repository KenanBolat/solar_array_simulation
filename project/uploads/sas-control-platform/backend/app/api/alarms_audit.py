from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Alarm, CommandAuditLog
from app.schemas.common import AlarmOut, AuditLogOut
from app.security import Principal, require

router = APIRouter(tags=["alarms-audit"])


@router.get("/api/alarms", response_model=list[AlarmOut])
async def list_alarms(active_only: bool = False, device_id: uuid.UUID | None = None,
                      session: AsyncSession = Depends(get_session), _=Depends(require("view"))):
    stmt = select(Alarm)
    if active_only:
        stmt = stmt.where(Alarm.cleared_utc.is_(None))
    if device_id:
        stmt = stmt.where(Alarm.device_id == device_id)
    return (await session.execute(stmt.order_by(Alarm.ts_utc.desc()).limit(500))).scalars().all()


@router.post("/api/alarms/{alarm_id}/ack", response_model=AlarmOut)
async def ack_alarm(alarm_id: uuid.UUID, principal: Principal = Depends(require("control_output")),
                    session: AsyncSession = Depends(get_session)):
    a = (await session.execute(select(Alarm).where(Alarm.id == alarm_id))).scalar_one()
    a.acknowledged = True
    a.acknowledged_by = principal.username
    await session.commit()
    return a


@router.get("/api/audit-log", response_model=list[AuditLogOut])
async def audit_log(device_id: uuid.UUID | None = None, limit: int = Query(200, le=2000),
                    session: AsyncSession = Depends(get_session), _=Depends(require("view"))):
    stmt = select(CommandAuditLog)
    if device_id:
        stmt = stmt.where(CommandAuditLog.device_id == device_id)
    return (await session.execute(
        stmt.order_by(CommandAuditLog.ts_utc.desc()).limit(limit))).scalars().all()
