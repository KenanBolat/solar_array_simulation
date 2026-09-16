from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class CommandTemplateRow(UUIDPk, Timestamps, Base):
    __tablename__ = "command_templates"
    template_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    hazardous: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotent: Mapped[bool] = mapped_column(Boolean, default=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)


class CommandRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "command_requests"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    template_id: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    requested_by: Mapped[str] = mapped_column(String(64), default="")
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class CommandResultRow(UUIDPk, Timestamps, Base):
    __tablename__ = "command_results"
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("command_requests.id"))
    status: Mapped[str] = mapped_column(String(16))
    scpi_sent: Mapped[str | None] = mapped_column(Text, nullable=True)
    scpi_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    readback_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")
    started_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int] = mapped_column(default=0)


class CommandAuditLog(UUIDPk, Base):
    """Append-only. No updated_at; rows are never mutated."""
    __tablename__ = "command_audit_log"
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    device_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(64), default="")
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
