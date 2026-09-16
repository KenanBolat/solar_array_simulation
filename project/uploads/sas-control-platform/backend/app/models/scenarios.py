from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk


class Scenario(UUIDPk, Timestamps, Base):
    __tablename__ = "scenarios"
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    versions: Mapped[list[ScenarioVersion]] = relationship(
        back_populates="scenario", lazy="selectin")


class ScenarioVersion(UUIDPk, Timestamps, Base):
    __tablename__ = "scenario_versions"
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|validated|approved|archived
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scenario: Mapped[Scenario] = relationship(back_populates="versions", lazy="selectin")
    nodes: Mapped[list[ScenarioNode]] = relationship(
        back_populates="version", lazy="selectin", cascade="all, delete-orphan")
    edges: Mapped[list[ScenarioEdge]] = relationship(
        back_populates="version", lazy="selectin", cascade="all, delete-orphan")


class ScenarioNode(UUIDPk, Base):
    __tablename__ = "scenario_nodes"
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_versions.id"))
    node_key: Mapped[str] = mapped_column(String(64))  # client-side id
    type: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(128), default="")
    x: Mapped[float] = mapped_column(Float, default=0)
    y: Mapped[float] = mapped_column(Float, default=0)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[ScenarioVersion] = relationship(back_populates="nodes")


class ScenarioEdge(UUIDPk, Base):
    __tablename__ = "scenario_edges"
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_versions.id"))
    edge_key: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(64), default="")
    version: Mapped[ScenarioVersion] = relationship(back_populates="edges")


class ScenarioRun(UUIDPk, Timestamps, Base):
    __tablename__ = "scenario_runs"
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenarios.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|running|paused|completed|aborted|failed
    dry_run: Mapped[bool] = mapped_column(default=False)
    target_device_ids: Mapped[list] = mapped_column(JSON, default=list)
    started_by: Mapped[str] = mapped_column(String(64), default="")
    started_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)


class ScenarioRunEvent(UUIDPk, Base):
    __tablename__ = "scenario_run_events"
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario_runs.id"))
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    node_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class SavedProfile(UUIDPk, Timestamps, Base):
    __tablename__ = "saved_profiles"
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)


class ConfigurationLimit(UUIDPk, Timestamps, Base):
    __tablename__ = "configuration_limits"
    scope: Mapped[str] = mapped_column(String(32), default="global")  # global|device
    device_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    max_voltage_v: Mapped[float] = mapped_column(Float, default=130.0)
    max_current_a: Mapped[float] = mapped_column(Float, default=20.0)
    updated_by: Mapped[str] = mapped_column(String(64), default="")
