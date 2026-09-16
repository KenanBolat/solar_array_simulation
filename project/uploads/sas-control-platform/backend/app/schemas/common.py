from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- topology ---
class ChannelOut(ORMModel):
    id: uuid.UUID
    index: int
    name: str


class ModuleOut(ORMModel):
    id: uuid.UUID
    slot: int
    name: str
    channels: list[ChannelOut] = []


class MainframeOut(ORMModel):
    id: uuid.UUID
    name: str
    model: str
    modules: list[ModuleOut] = []


class RackOut(ORMModel):
    id: uuid.UUID
    name: str
    location: str
    position: int


class RackDetailOut(RackOut):
    mainframes: list[MainframeOut] = []


class ConnectionProfileOut(ORMModel):
    id: uuid.UUID
    name: str
    driver_kind: str
    connection_type: str
    visa_resource: str
    fault_profile: str


class DeviceOut(ORMModel):
    id: uuid.UUID
    name: str
    rack_id: uuid.UUID
    mainframe_id: uuid.UUID | None
    module_id: uuid.UUID | None
    channel_id: uuid.UUID | None
    level: str
    last_state: dict = {}
    connection_profile: ConnectionProfileOut


class DeviceStateOut(BaseModel):
    device_id: uuid.UUID
    connected: bool
    device_state: str
    output_enabled: bool
    remote_mode: bool
    voltage_v: float
    current_a: float
    power_w: float
    device_mode: str
    alarm_state: str | None
    firmware: str
    last_comm_utc: datetime | None
    comm_health: str
    simulation: bool


# --- commands ---
class CommandIn(BaseModel):
    template_id: str
    params: dict = Field(default_factory=dict)
    confirmed: bool = False
    correlation_id: str | None = None


class OutputIn(BaseModel):
    enabled: bool
    confirmed: bool = False


class CommandResultOut(ORMModel):
    id: uuid.UUID
    request_id: uuid.UUID
    status: str
    scpi_sent: str | None
    scpi_response: str | None
    readback_verified: bool
    message: str
    started_utc: datetime
    finished_utc: datetime
    latency_ms: int


class CommandTemplateOut(BaseModel):
    id: str
    title: str
    description: str
    hazardous: bool
    requires_confirmation: bool
    idempotent: bool
    verified: bool
    parameters: dict


class AuditLogOut(ORMModel):
    id: uuid.UUID
    ts_utc: datetime
    actor: str
    action: str
    device_id: uuid.UUID | None
    template_id: str | None
    correlation_id: str
    outcome: str
    detail: dict


class AlarmOut(ORMModel):
    id: uuid.UUID
    device_id: uuid.UUID
    ts_utc: datetime
    severity: str
    code: str
    message: str
    acknowledged: bool
    cleared_utc: datetime | None


class MeasurementOut(BaseModel):
    timestamp_utc: datetime
    device_id: uuid.UUID
    voltage_v: float
    current_a: float
    power_w: float
    output_enabled: bool
    device_state: str
    alarm_state: str | None
    quality_flag: str
