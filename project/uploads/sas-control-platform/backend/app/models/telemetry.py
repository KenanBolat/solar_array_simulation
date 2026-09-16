from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPk


class Measurement(Base):
    """TimescaleDB hypertable. Composite PK (timestamp, device) -- required
    because hypertables partition on the time column."""
    __tablename__ = "measurements"
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    device_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    rack_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    mainframe_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    module_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    voltage_v: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)
    power_w: Mapped[float] = mapped_column(Float)
    output_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    device_state: Mapped[str] = mapped_column(String(24), default="unknown")
    alarm_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quality_flag: Mapped[str] = mapped_column(String(12), default="good")
    scenario_run_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), default="telemetry")

    __table_args__ = (
        Index("ix_measurements_device_time", "device_id", "timestamp_utc"),
    )


class Alarm(UUIDPk, Base):
    __tablename__ = "alarms"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # info|warning|alarm|critical
    code: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cleared_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Event(UUIDPk, Base):
    """Append-only system event stream (config changes, approvals, etc.)."""
    __tablename__ = "events"
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str] = mapped_column(String(32))  # config|approval|auth|scenario|device
    actor: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
