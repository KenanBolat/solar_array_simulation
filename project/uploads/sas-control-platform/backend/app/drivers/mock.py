"""MockE4360Driver -- realistic synthetic instrument.

Generates correlated V/I/P telemetry from a simple solar-array model,
supports output ON/OFF, profiles, simulated failures, delayed responses,
disconnected/warning/alarm states. Used everywhere until SAS_HARDWARE_ENABLED
is true AND a device is bound to the real driver.
"""
from __future__ import annotations

import asyncio
import math
import random
from typing import Any

from app.drivers.base import (
    CommandResult,
    CommandStatus,
    CommandTemplate,
    DeviceState,
    DeviceStateSnapshot,
    DriverCapabilities,
    InstrumentDriver,
    MeasurementSnapshot,
    utcnow,
)
from app.drivers.templates import (
    CAPABILITY_MAP_VERSION,
    STANDARD_TEMPLATES,
)


class MockE4360Driver(InstrumentDriver):
    driver_kind = "mock"

    def __init__(self, device_id: str, resource: str, soft_limits: dict[str, float],
                 fault_profile: str = "nominal", seed: int | None = None):
        super().__init__(device_id, resource, soft_limits)
        self._rng = random.Random(seed if seed is not None else hash(device_id) & 0xFFFF)
        self._connected = False
        self._output = False
        self._remote = True
        self._t = self._rng.random() * 1000.0
        self._fault_profile = fault_profile  # nominal | flaky | offline | warning | alarm
        # SAS curve parameters (defaults; can be overwritten by profiles)
        self._voc = 100.0 + self._rng.uniform(-5, 5)
        self._vmp = self._voc * 0.82
        self._isc = 8.0 + self._rng.uniform(-1, 1)
        self._imp = self._isc * 0.92
        self._set_voltage = self._vmp
        self._last_comm = None

    # --- lifecycle -----------------------------------------------------
    async def connect(self) -> None:
        await asyncio.sleep(0.02)
        if self._fault_profile == "offline":
            raise ConnectionError(f"[SIM] device {self.device_id} unreachable")
        self._connected = True
        self._last_comm = utcnow()

    async def disconnect(self) -> None:
        self._connected = False

    async def identify(self) -> str:
        await self._maybe_delay()
        self._touch()
        return f"SIM,Solar Array Simulator,{self.device_id},FW-SIM-1.4.2"

    # --- read paths (idempotent, safe to retry) ------------------------
    def _curve(self) -> tuple[float, float]:
        """Return (voltage, current) from a simplified I-V curve at the
        current operating point, with small dynamic noise."""
        if not self._output:
            return 0.0, 0.0
        v = min(self._set_voltage, self._voc)
        # piecewise-ish curve: current near Isc below Vmp, drops toward Voc
        if v <= self._vmp:
            i = self._isc - (self._isc - self._imp) * (v / max(self._vmp, 1e-6))
        else:
            frac = (v - self._vmp) / max(self._voc - self._vmp, 1e-6)
            i = self._imp * (1.0 - frac)
        # dynamic wobble + slow drift
        self._t += 0.15
        wobble = 1.0 + 0.012 * math.sin(self._t) + self._rng.uniform(-0.004, 0.004)
        i = max(0.0, i * wobble)
        v = max(0.0, v * (1.0 + self._rng.uniform(-0.002, 0.002)))
        return v, i

    def _state_enum(self) -> DeviceState:
        if not self._connected:
            return DeviceState.OFFLINE
        if self._fault_profile == "alarm":
            return DeviceState.ALARM
        if self._fault_profile == "warning":
            return DeviceState.WARNING
        if self._output:
            return DeviceState.OUTPUT_ENABLED
        return DeviceState.ONLINE

    def _alarm(self) -> str | None:
        if self._fault_profile == "alarm":
            return "OVERTEMP"
        if self._fault_profile == "warning":
            return "FAN_DEGRADED"
        return None

    async def read_state(self) -> DeviceStateSnapshot:
        await self._maybe_delay()
        if not self._connected:
            return DeviceStateSnapshot(
                connected=False, device_state=DeviceState.OFFLINE, output_enabled=False,
                remote_mode=self._remote, voltage_v=0, current_a=0, power_w=0,
                device_mode="SAS", alarm_state=None, firmware="FW-SIM-1.4.2",
                last_comm_utc=self._last_comm, comm_health="lost",
            )
        self._touch()
        v, i = self._curve()
        return DeviceStateSnapshot(
            connected=True, device_state=self._state_enum(), output_enabled=self._output,
            remote_mode=self._remote, voltage_v=round(v, 3), current_a=round(i, 3),
            power_w=round(v * i, 3), device_mode="SAS", alarm_state=self._alarm(),
            firmware="FW-SIM-1.4.2", last_comm_utc=self._last_comm,
            comm_health="degraded" if self._fault_profile == "flaky" else "healthy",
        )

    async def read_measurements(self) -> MeasurementSnapshot:
        await self._maybe_delay()
        if not self._connected:
            return MeasurementSnapshot(
                timestamp_utc=utcnow(), voltage_v=0, current_a=0, power_w=0,
                output_enabled=False, device_state=DeviceState.OFFLINE,
                alarm_state=None, quality_flag="bad", source_type="telemetry",
            )
        self._touch()
        v, i = self._curve()
        return MeasurementSnapshot(
            timestamp_utc=utcnow(), voltage_v=round(v, 3), current_a=round(i, 3),
            power_w=round(v * i, 3), output_enabled=self._output,
            device_state=self._state_enum(), alarm_state=self._alarm(),
            quality_flag="suspect" if self._fault_profile == "flaky" else "good",
            source_type="telemetry",
        )

    # --- write paths (state changing, with readback verification) ------
    async def set_output_state(self, enabled: bool) -> CommandResult:
        return await self._run_write(
            f"output_{'on' if enabled else 'off'}",
            lambda: setattr(self, "_output", enabled),
            verify=lambda: self._output == enabled,
        )

    async def apply_profile(self, profile: dict[str, Any]) -> CommandResult:
        def _apply():
            self._isc = float(profile.get("isc_a", self._isc))
            self._imp = float(profile.get("imp_a", self._imp))
            self._voc = float(profile.get("voc_v", self._voc))
            self._vmp = float(profile.get("vmp_v", self._vmp))
            self._set_voltage = self._vmp
        return await self._run_write("apply_profile", _apply, verify=lambda: True)

    async def safe_shutdown(self) -> CommandResult:
        return await self._run_write(
            "safe_shutdown",
            lambda: setattr(self, "_output", False),
            verify=lambda: self._output is False,
        )

    async def execute_validated_command(
        self, template: CommandTemplate, params: dict[str, Any]
    ) -> CommandResult:
        self.validate_params(template, params)
        tid = template.id
        if tid == "identify":
            ident = await self.identify()
            return self._ok(tid, scpi="*IDN?", resp=ident)
        if tid == "read_measurements":
            m = await self.read_measurements()
            return self._ok(tid, scpi="MEAS?", resp=f"{m.voltage_v},{m.current_a},{m.power_w}")
        if tid == "set_voltage":
            return await self._run_write(
                tid, lambda: setattr(self, "_set_voltage", float(params["voltage_v"])),
                verify=lambda: abs(self._set_voltage - float(params["voltage_v"])) < 1e-6,
            )
        if tid == "set_current_limit":
            return await self._run_write(
                tid, lambda: setattr(self, "_imp", float(params["current_a"])),
                verify=lambda: True)
        if tid == "configure_sas_table":
            return await self.apply_profile(params)
        if tid in ("output_on", "output_off"):
            return await self.set_output_state(tid == "output_on")
        if tid == "safe_shutdown":
            return await self.safe_shutdown()
        return self._reject(tid, "command not implemented in mock")

    def get_capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            model="SAS-SIM (generic)", driver_kind=self.driver_kind, simulation=True,
            firmware="FW-SIM-1.4.2", max_voltage_v=self.soft_limits.get("max_voltage_v", 130.0),
            max_current_a=self.soft_limits.get("max_current_a", 20.0),
            supports_solar_array_table=True, command_templates=list(STANDARD_TEMPLATES),
            capability_map_version=CAPABILITY_MAP_VERSION,
        )

    # --- internals -----------------------------------------------------
    def _touch(self):
        self._last_comm = utcnow()

    async def _maybe_delay(self):
        if self._fault_profile == "flaky":
            await asyncio.sleep(self._rng.uniform(0.05, 0.4))
            if self._rng.random() < 0.05:
                raise TimeoutError("[SIM] transient comms timeout")
        else:
            await asyncio.sleep(0.01)

    async def _run_write(self, tid, mutate, verify) -> CommandResult:
        start = utcnow()
        if not self._connected:
            return self._reject(tid, "device not connected", start)
        if self._fault_profile == "alarm":
            return self._fail(tid, "device in ALARM; write rejected", start)
        try:
            await self._maybe_delay()
            mutate()
            ok = verify()
            fin = utcnow()
            return CommandResult(
                status=CommandStatus.COMPLETED if ok else CommandStatus.FAILED,
                scpi_sent=f"[SIM:{tid}]", scpi_response="OK" if ok else "READBACK_MISMATCH",
                readback_verified=ok, message="ok" if ok else "readback verification failed",
                started_utc=start, finished_utc=fin,
            )
        except (TimeoutError, ConnectionError) as exc:
            return CommandResult(
                status=CommandStatus.TIMED_OUT, scpi_sent=f"[SIM:{tid}]", scpi_response=None,
                readback_verified=False, message=str(exc), started_utc=start, finished_utc=utcnow())

    def _ok(self, tid, scpi, resp) -> CommandResult:
        now = utcnow()
        return CommandResult(CommandStatus.COMPLETED, scpi, resp, True, "ok", now, now)

    def _fail(self, tid, msg, start=None) -> CommandResult:
        start = start or utcnow()
        return CommandResult(CommandStatus.FAILED, f"[SIM:{tid}]", None, False, msg, start, utcnow())

    def _reject(self, tid, msg, start=None) -> CommandResult:
        start = start or utcnow()
        return CommandResult(CommandStatus.REJECTED, None, None, False, msg, start, utcnow())
