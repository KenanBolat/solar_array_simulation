from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NodeIn(BaseModel):
    node_key: str
    type: str
    label: str = ""
    x: float = 0
    y: float = 0
    config: dict = Field(default_factory=dict)


class EdgeIn(BaseModel):
    edge_key: str
    source: str
    target: str
    label: str = ""


class ScenarioIn(BaseModel):
    name: str
    description: str = ""
    nodes: list[NodeIn] = Field(default_factory=list)
    edges: list[EdgeIn] = Field(default_factory=list)


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
    current_version: int


class ScenarioDetailOut(ScenarioOut):
    status: str
    nodes: list[NodeIn]
    edges: list[EdgeIn]


class ValidationOut(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class RunIn(BaseModel):
    target_device_ids: list[uuid.UUID]
    dry_run: bool = False
    confirmed: bool = False


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    scenario_id: uuid.UUID
    version: int
    status: str
    dry_run: bool
    progress: float
    started_utc: datetime | None
    finished_utc: datetime | None


class RunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ts_utc: datetime
    node_key: str | None
    level: str
    message: str
