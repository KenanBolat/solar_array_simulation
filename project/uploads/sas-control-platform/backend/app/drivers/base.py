"""InstrumentDriver abstraction.

Real SCPI hardware is hidden behind this interface so the rest of the
application never speaks SCPI directly. The MVP ships a fully functional
MockE4360Driver and a clearly-marked E4360Driver placeholder.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(UTC)


class DeviceState(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ARMED = "armed"
    OUTPUT_ENABLED = "output_enabled"
    RUNNING_SCENARIO = "running_scenario"
    WARNING = "warning"
    ALARM = "alarm"
    UNKNOWN = "unknown"


class CommandStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


# --- Errors -----------------------------------------------------------------
class DriverError(Exception):
    """Generic driver / instrument communication error."""


class CommandNotSupportedError(DriverError):
    """Raised when a command id is not present in the capability map."""


class UnsafeParameterError(DriverError):
    """Raised when a parameter is outside configured soft limits."""


# --- Value objects ----------------------------------------------------------
@dataclass(slots=True)
class CommandTemplate:
    """A validated, named command. Drivers never accept free-form SCPI from
    normal users -- only template ids with validated parameters."""

    id: str
    title: str
    description: str
    hazardous: bool = False
    requires_confirmation: bool = False
    # Parameter name -> {type, min, max, unit, required}
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Whether retrying this command is safe (idempotent read-style ops).
    idempotent: bool = False
    # The underlying SCPI string is intentionally NOT defined here for the
    # mock; the real driver maps id -> verified SCPI from the manual.
    verified: bool = False  # True only once confirmed against the manual


@dataclass(slots=True)
class DriverCapabilities:
    model: str
    driver_kind: str  # "mock" | "e4360"
    simulation: bool
    firmware: str
    max_voltage_v: float
    max_current_a: float
    supports_solar_array_table: bool
    command_templates: list[CommandTemplate] = field(default_factory=list)
    capability_map_version: str = "0.0.0"


@dataclass(slots=True)
class MeasurementSnapshot:
    timestamp_utc: datetime
    voltage_v: float
    current_a: float
    power_w: float
    output_enabled: bool
    device_state: DeviceState
    alarm_state: str | None
    quality_flag: str = "good"  # good | stale | suspect | bad
    source_type: str = "telemetry"


@dataclass(slots=True)
class DeviceStateSnapshot:
    connected: bool
    device_state: DeviceState
    output_enabled: bool
    remote_mode: bool
    voltage_v: float
    current_a: float
    power_w: float
    device_mode: str
    alarm_state: str | None
    firmware: str
    last_comm_utc: datetime | None
    comm_health: str  # healthy | degraded | lost


@dataclass(slots=True)
class CommandResult:
    status: CommandStatus
    scpi_sent: str | None
    scpi_response: str | None
    readback_verified: bool
    message: str
    started_utc: datetime
    finished_utc: datetime
    detail: dict[str, Any] = field(default_factory=dict)


class InstrumentDriver(abc.ABC):
    """Contract implemented by every driver.

    Implementations MUST be safe to call from a single serial command queue
    per physical instrument (see services/command_queue.py). They must never
    be invoked concurrently for write operations against the same device.
    """

    def __init__(self, device_id: str, resource: str, soft_limits: dict[str, float]):
        self.device_id = device_id
        self.resource = resource
        self.soft_limits = soft_limits

    @abc.abstractmethod
    async def connect(self) -> None: ...

    @abc.abstractmethod
    async def disconnect(self) -> None: ...

    @abc.abstractmethod
    async def identify(self) -> str: ...

    @abc.abstractmethod
    async def read_state(self) -> DeviceStateSnapshot: ...

    @abc.abstractmethod
    async def read_measurements(self) -> MeasurementSnapshot: ...

    @abc.abstractmethod
    async def execute_validated_command(
        self, template: CommandTemplate, params: dict[str, Any]
    ) -> CommandResult: ...

    @abc.abstractmethod
    async def set_output_state(self, enabled: bool) -> CommandResult: ...

    @abc.abstractmethod
    async def apply_profile(self, profile: dict[str, Any]) -> CommandResult: ...

    @abc.abstractmethod
    async def safe_shutdown(self) -> CommandResult: ...

    @abc.abstractmethod
    def get_capabilities(self) -> DriverCapabilities: ...

    # --- Shared validation helper (used by both drivers) ---
    def validate_params(self, template: CommandTemplate, params: dict[str, Any]) -> None:
        for name, spec in template.parameters.items():
            if spec.get("required", False) and name not in params:
                raise UnsafeParameterError(f"Missing required parameter '{name}'")
            if name not in params:
                continue
            value = params[name]
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None and value < lo:
                raise UnsafeParameterError(f"{name}={value} below soft minimum {lo}")
            if hi is not None and value > hi:
                raise UnsafeParameterError(f"{name}={value} above soft maximum {hi}")
        # Cross-check against global soft limits regardless of template.
        if "voltage_v" in params and params["voltage_v"] > self.soft_limits.get("max_voltage_v", 1e9):
            raise UnsafeParameterError("voltage exceeds device soft limit")
        if "current_a" in params and params["current_a"] > self.soft_limits.get("max_current_a", 1e9):
            raise UnsafeParameterError("current exceeds device soft limit")
