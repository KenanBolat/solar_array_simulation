"""E4360Driver — production adapter for LAN (raw SOCKET) transport.

STATUS: structurally complete, functionally gated.

Every method below is fully implemented. The driver is inert only because the
SCPI strings in `_SCPI_MAP` are `None` and marked `verified=False`. Fill in a
string from the official Keysight E4360 programming manual, flip `verified`,
and that one operation goes live — nothing else needs to change.

  DO NOT invent SCPI syntax. If you have not read it in the manual for YOUR
  firmware revision, leave it None. `_require()` refuses to transmit
  unverified operations, which is what keeps this file safe to deploy
  half-finished.

Read-only IEEE-488.2 / SCPI-99 standard queries (`*IDN?`, `SYST:ERR?`, `*CLS`,
`*OPC?`) are pre-marked verified: they are not vendor-specific and cannot
change instrument output state. That is enough to connect, identify and read
the error queue before any write command has been confirmed.

Transport: raw TCP socket (default SCPI port 5025), resource of the form
    TCPIP0::192.168.10.21::5025::SOCKET

  RAW SOCKET GOTCHA: unlike VXI-11/INSTR, a SOCKET session has NO built-in
  message termination. `read_termination` and `write_termination` MUST be set
  explicitly or every query blocks until timeout. Both are set in `connect()`.

Concurrency: pyvisa is blocking, so every I/O call is dispatched through
`asyncio.to_thread` to avoid stalling the event loop. The command queue
already guarantees one writer per instrument.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.drivers.base import (
    CommandNotSupportedError,
    CommandResult,
    CommandStatus,
    CommandTemplate,
    DeviceState,
    DeviceStateSnapshot,
    DriverCapabilities,
    DriverError,
    InstrumentDriver,
    MeasurementSnapshot,
    utcnow,
)
from app.drivers.templates import CAPABILITY_MAP_VERSION, STANDARD_TEMPLATES

# Default raw-socket SCPI port and I/O settings.
DEFAULT_SOCKET_PORT = 5025
READ_TERMINATION = "\n"
WRITE_TERMINATION = "\n"
DEFAULT_TIMEOUT_MS = 5000

# Tolerance when verifying a setpoint readback (absolute, in the value's unit).
READBACK_TOLERANCE = 0.05


@dataclass
class ScpiOp:
    """One instrument operation.

    write     command sent to change state. May contain `{value}` and `{ch}`.
    query     query form used to READ a value. May contain `{ch}`.
    readback  query used to confirm a `write` took effect. May contain `{ch}`.
    verified  True ONLY after the string is confirmed against the manual.
    note      what to look up in the manual, for whoever fills this in.
    """

    write: str | None = None
    query: str | None = None
    readback: str | None = None
    verified: bool = False
    note: str = ""


# -----------------------------------------------------------------------------
# FILL-IN TABLE
#
# For each entry: read the manual, paste the exact string, set verified=True.
# Use `{ch}` where the channel selector goes and `{value}` for the parameter.
# Pair every `write` with a `readback` query — the platform verifies setpoints
# after every state change and will report readback_verified=False without one.
# -----------------------------------------------------------------------------
_SCPI_MAP: dict[str, ScpiOp] = {
    # --- standard, read-only, safe to enable before anything else ----------
    "identify": ScpiOp(
        query="*IDN?",
        verified=True,
        note="IEEE-488.2 standard. Confirm the response field order for your firmware.",
    ),
    "error_query": ScpiOp(
        query="SYST:ERR?",
        verified=True,
        note="SCPI-99 standard error queue read. Confirm supported; harmless if not.",
    ),
    "clear_status": ScpiOp(
        write="*CLS",
        verified=True,
        note="IEEE-488.2 standard. Clears status/error queue; does not affect output.",
    ),
    "operation_complete": ScpiOp(
        query="*OPC?",
        verified=True,
        note="IEEE-488.2 standard. Used to serialise after writes.",
    ),
    # --- measurements ------------------------------------------------------
    "read_voltage": ScpiOp(
        query=None,
        note="MANUAL: measured output voltage query, incl. channel syntax. "
        "Likely in the MEASure subsystem. Confirm units (V) and whether a "
        "combined V/I/P query exists.",
    ),
    "read_current": ScpiOp(
        query=None,
        note="MANUAL: measured output current query, incl. channel syntax. Confirm units (A).",
    ),
    "read_power": ScpiOp(
        query=None,
        note="MANUAL: measured power query IF the instrument provides one. "
        "If not, leave None — the driver computes P = V x I instead.",
    ),
    # --- setpoints ---------------------------------------------------------
    "set_voltage": ScpiOp(
        write=None,
        readback=None,
        note="MANUAL: programmed output voltage command + the query that reads "
        "the setpoint back. Confirm range, units, and SAS-mode interaction.",
    ),
    "set_current_limit": ScpiOp(
        write=None,
        readback=None,
        note="MANUAL: programmed current limit command + setpoint readback query.",
    ),
    # --- solar-array simulation curve --------------------------------------
    # The SAS curve is defined by four parameters. Confirm whether your firmware
    # takes them in one command or four, and the exact parameter ORDER — a
    # transposed Isc/Imp will silently produce a wrong curve.
    "sas_isc": ScpiOp(write=None, readback=None, note="MANUAL: short-circuit current (Isc) parameter."),
    "sas_imp": ScpiOp(write=None, readback=None, note="MANUAL: max-power current (Imp) parameter."),
    "sas_voc": ScpiOp(write=None, readback=None, note="MANUAL: open-circuit voltage (Voc) parameter."),
    "sas_vmp": ScpiOp(write=None, readback=None, note="MANUAL: max-power voltage (Vmp) parameter."),
    "sas_mode_on": ScpiOp(
        write=None,
        readback=None,
        note="MANUAL: command that puts the channel into solar-array/SAS "
        "simulation mode, if it is a separate mode selection.",
    ),
    # --- output state ------------------------------------------------------
    "output_on": ScpiOp(
        write=None,
        readback=None,
        note="MANUAL: output enable command + output-state query. Also note any "
        "settling time before the state query reads back correctly.",
    ),
    "output_off": ScpiOp(
        write=None,
        readback=None,
        note="MANUAL: output disable command (readback query is usually the same "
        "as output_on's).",
    ),
    # --- channel selection -------------------------------------------------
    "select_channel": ScpiOp(
        write=None,
        note="MANUAL: how a logical unit maps to mainframe + slot + output, and "
        "the channel selector syntax. If channels are addressed inline (e.g. a "
        "suffix on each command) leave this None and put `{ch}` in each string "
        "instead.",
    ),
}


class E4360Driver(InstrumentDriver):
    driver_kind = "e4360"

    def __init__(
        self,
        device_id: str,
        resource: str,
        soft_limits: dict[str, float],
        channel: int | str | None = None,
    ):
        super().__init__(device_id, resource, soft_limits)
        self._inst: Any = None
        self._rm: Any = None
        self._channel = channel if channel is not None else 1
        self._firmware = "unknown"
        self._last_comm = None

    # ------------------------------------------------------------------ setup
    async def connect(self) -> None:
        try:
            import pyvisa
        except ImportError as exc:  # pragma: no cover
            raise DriverError(
                "PyVISA not installed on the API host; cannot use real hardware"
            ) from exc

        def _open() -> Any:
            rm = pyvisa.ResourceManager()
            inst = rm.open_resource(self.resource)
            # REQUIRED for raw SOCKET sessions — see module docstring.
            if "SOCKET" in self.resource.upper():
                inst.read_termination = READ_TERMINATION
                inst.write_termination = WRITE_TERMINATION
            inst.timeout = DEFAULT_TIMEOUT_MS
            return rm, inst

        try:
            self._rm, self._inst = await asyncio.to_thread(_open)
        except Exception as exc:  # pragma: no cover
            raise DriverError(f"could not open {self.resource}: {exc}") from exc

        # Identify immediately: proves the link and the termination settings.
        try:
            self._firmware = await self.identify()
        except Exception as exc:
            await self.disconnect()
            raise DriverError(
                f"opened {self.resource} but *IDN? failed ({exc}). For SOCKET "
                f"resources this usually means a wrong port or termination."
            ) from exc

    async def disconnect(self) -> None:
        def _close() -> None:
            if self._inst is not None:
                self._inst.close()
            if self._rm is not None:
                self._rm.close()

        if self._inst is not None or self._rm is not None:
            await asyncio.to_thread(_close)
        self._inst = None
        self._rm = None

    # ------------------------------------------------------- gating + plumbing
    def _require(self, op_id: str, kind: str = "write") -> str:
        op = _SCPI_MAP.get(op_id)
        if op is None:
            raise CommandNotSupportedError(f"no SCPI mapping defined for '{op_id}'")
        if not op.verified:
            raise CommandNotSupportedError(
                f"'{op_id}' is not verified against the E4360 programming manual "
                f"— refusing to transmit. {op.note}"
            )
        s = getattr(op, kind)
        if s is None:
            raise CommandNotSupportedError(
                f"'{op_id}' has no {kind} string defined. {op.note}"
            )
        return s

    def _has(self, op_id: str, kind: str = "write") -> bool:
        op = _SCPI_MAP.get(op_id)
        return bool(op and op.verified and getattr(op, kind) is not None)

    def _fmt(self, template: str, value: Any = None) -> str:
        return template.format(ch=self._channel, value=value)

    async def _write(self, scpi: str) -> None:
        if self._inst is None:
            raise DriverError("not connected")
        await asyncio.to_thread(self._inst.write, scpi)
        self._last_comm = utcnow()

    async def _query(self, scpi: str) -> str:
        if self._inst is None:
            raise DriverError("not connected")
        raw = await asyncio.to_thread(self._inst.query, scpi)
        self._last_comm = utcnow()
        return str(raw).strip()

    async def _query_float(self, scpi: str) -> float:
        raw = await self._query(scpi)
        # Instruments may answer "2.80000000E+01" or "28.0,4.2" for combined queries.
        first = raw.split(",")[0].strip()
        try:
            return float(first)
        except ValueError as exc:
            raise DriverError(f"expected a number from '{scpi}', got '{raw}'") from exc

    async def _check_error_queue(self) -> str | None:
        """Read one entry from the instrument error queue, if supported."""
        if not self._has("error_query", "query"):
            return None
        try:
            resp = await self._query(_SCPI_MAP["error_query"].query or "")
        except Exception:
            return None
        # Convention: "0,\"No error\"" means clean.
        return None if resp.startswith("0,") or resp.startswith("+0,") else resp

    async def _select_channel(self) -> None:
        """Send an explicit channel selection if the instrument needs one."""
        if self._has("select_channel", "write"):
            await self._write(self._fmt(_SCPI_MAP["select_channel"].write or ""))

    # ---------------------------------------------------------------- reading
    async def identify(self) -> str:
        scpi = self._require("identify", "query")
        return await self._query(scpi)

    async def read_measurements(self) -> MeasurementSnapshot:
        await self._select_channel()
        v = await self._query_float(self._fmt(self._require("read_voltage", "query")))
        i = await self._query_float(self._fmt(self._require("read_current", "query")))
        if self._has("read_power", "query"):
            p = await self._query_float(self._fmt(_SCPI_MAP["read_power"].query or ""))
        else:
            p = v * i
        out = await self._read_output_state()
        err = await self._check_error_queue()
        return MeasurementSnapshot(
            timestamp_utc=utcnow(),
            voltage_v=v,
            current_a=i,
            power_w=p,
            output_enabled=out,
            device_state=DeviceState.OUTPUT_ENABLED if out else DeviceState.ONLINE,
            alarm_state=err,
            quality_flag="good",
        )

    async def _read_output_state(self) -> bool:
        if not self._has("output_on", "readback"):
            return False
        raw = await self._query(self._fmt(_SCPI_MAP["output_on"].readback or ""))
        return raw.strip() in {"1", "ON", "on", "+1"}

    async def read_state(self) -> DeviceStateSnapshot:
        m = await self.read_measurements()
        return DeviceStateSnapshot(
            connected=self._inst is not None,
            device_state=m.device_state,
            output_enabled=m.output_enabled,
            remote_mode=True,
            voltage_v=m.voltage_v,
            current_a=m.current_a,
            power_w=m.power_w,
            device_mode="sas",
            alarm_state=m.alarm_state,
            firmware=self._firmware,
            last_comm_utc=self._last_comm,
            comm_health="healthy" if self._inst is not None else "lost",
        )

    # ---------------------------------------------------------------- writing
    async def _write_with_readback(
        self, op_id: str, value: Any = None, expect: float | None = None
    ) -> CommandResult:
        """Send a write, then verify it via the paired readback query."""
        started = utcnow()
        scpi = self._fmt(self._require(op_id, "write"), value)
        await self._select_channel()
        await self._write(scpi)

        # Serialise if the instrument supports *OPC?.
        if self._has("operation_complete", "query"):
            try:
                await self._query(_SCPI_MAP["operation_complete"].query or "")
            except Exception:
                pass

        err = await self._check_error_queue()
        if err:
            return CommandResult(
                status=CommandStatus.FAILED,
                scpi_sent=scpi,
                scpi_response=err,
                readback_verified=False,
                message=f"instrument reported an error: {err}",
                started_utc=started,
                finished_utc=utcnow(),
            )

        verified = False
        response: str | None = None
        if self._has(op_id, "readback"):
            rb = self._fmt(_SCPI_MAP[op_id].readback or "")
            response = await self._query(rb)
            if expect is not None:
                try:
                    verified = abs(float(response.split(",")[0]) - expect) <= READBACK_TOLERANCE
                except ValueError:
                    verified = False
            else:
                verified = True

        return CommandResult(
            status=CommandStatus.COMPLETED,
            scpi_sent=scpi,
            scpi_response=response,
            readback_verified=verified,
            message="" if verified or expect is None else "readback did not match setpoint",
            started_utc=started,
            finished_utc=utcnow(),
        )

    async def execute_validated_command(
        self, template: CommandTemplate, params: dict[str, Any]
    ) -> CommandResult:
        self.validate_params(template, params)
        tid = template.id

        if tid == "identify":
            started = utcnow()
            ident = await self.identify()
            return CommandResult(
                status=CommandStatus.COMPLETED,
                scpi_sent=_SCPI_MAP["identify"].query,
                scpi_response=ident,
                readback_verified=True,
                message="",
                started_utc=started,
                finished_utc=utcnow(),
            )

        if tid == "read_measurements":
            started = utcnow()
            m = await self.read_measurements()
            return CommandResult(
                status=CommandStatus.COMPLETED,
                scpi_sent="<measurement read>",
                scpi_response=f"{m.voltage_v},{m.current_a},{m.power_w}",
                readback_verified=True,
                message="",
                started_utc=started,
                finished_utc=utcnow(),
            )

        if tid == "set_voltage":
            v = float(params["voltage_v"])
            return await self._write_with_readback("set_voltage", v, expect=v)

        if tid == "set_current_limit":
            a = float(params["current_a"])
            return await self._write_with_readback("set_current_limit", a, expect=a)

        if tid == "configure_sas_table":
            return await self.apply_profile(params)

        if tid in {"output_on", "output_off"}:
            return await self.set_output_state(tid == "output_on")

        if tid == "apply_profile":
            return await self.apply_profile(params)

        if tid == "safe_shutdown":
            return await self.safe_shutdown()

        raise CommandNotSupportedError(f"template '{tid}' is not handled by this driver")

    async def set_output_state(self, enabled: bool) -> CommandResult:
        return await self._write_with_readback("output_on" if enabled else "output_off")

    async def apply_profile(self, profile: dict[str, Any]) -> CommandResult:
        """Apply the four SAS curve parameters, then the mode selection.

        Ordering matters: curve parameters are set BEFORE the output is
        enabled elsewhere, and the mode selection comes last so the curve is
        fully defined when the channel switches into SAS mode. Confirm the
        required sequence in the manual — some firmware rejects parameters
        written while the channel is already in SAS mode.
        """
        started = utcnow()
        sent: list[str] = []
        for key, op_id in (
            ("isc_a", "sas_isc"),
            ("imp_a", "sas_imp"),
            ("voc_v", "sas_voc"),
            ("vmp_v", "sas_vmp"),
        ):
            if key not in profile:
                continue
            value = float(profile[key])
            res = await self._write_with_readback(op_id, value, expect=value)
            sent.append(res.scpi_sent or op_id)
            if res.status is not CommandStatus.COMPLETED:
                return CommandResult(
                    status=res.status,
                    scpi_sent="; ".join(sent),
                    scpi_response=res.scpi_response,
                    readback_verified=False,
                    message=f"aborted at {op_id}: {res.message}",
                    started_utc=started,
                    finished_utc=utcnow(),
                )

        if self._has("sas_mode_on", "write"):
            res = await self._write_with_readback("sas_mode_on")
            sent.append(res.scpi_sent or "sas_mode_on")

        return CommandResult(
            status=CommandStatus.COMPLETED,
            scpi_sent="; ".join(sent),
            scpi_response=None,
            readback_verified=True,
            message="",
            started_utc=started,
            finished_utc=utcnow(),
        )

    async def safe_shutdown(self) -> CommandResult:
        """Best-effort move to a safe state.

        Output-off is attempted FIRST and unconditionally — it is the action
        that actually makes the unit safe. Reducing the current limit is a
        secondary nicety and its failure must not mask a successful output-off.
        """
        started = utcnow()
        steps: list[str] = []
        try:
            off = await self.set_output_state(False)
            steps.append(off.scpi_sent or "output_off")
            if off.status is not CommandStatus.COMPLETED:
                raise DriverError(off.message or "output_off did not complete")
        except Exception as exc:
            return CommandResult(
                status=CommandStatus.FAILED,
                scpi_sent="; ".join(steps) or None,
                scpi_response=None,
                readback_verified=False,
                message=(
                    f"SAFE SHUTDOWN FAILED: could not disable output ({exc}). "
                    f"Use the physical interlock or instrument front panel."
                ),
                started_utc=started,
                finished_utc=utcnow(),
            )

        if self._has("set_current_limit", "write"):
            try:
                res = await self._write_with_readback("set_current_limit", 0.0, expect=0.0)
                steps.append(res.scpi_sent or "set_current_limit")
            except Exception:
                pass  # output is already off; this is non-critical

        return CommandResult(
            status=CommandStatus.COMPLETED,
            scpi_sent="; ".join(steps),
            scpi_response=None,
            readback_verified=True,
            message="output disabled",
            started_utc=started,
            finished_utc=utcnow(),
        )

    # ----------------------------------------------------------- capabilities
    def get_capabilities(self) -> DriverCapabilities:
        """Report per-template verification state.

        The UI surfaces `verified` per template ("SCPI verified" vs
        "SCPI unverified"), so this is what tells an operator which commands
        are actually live on real hardware.
        """
        # A template is live only if every operation it depends on is verified.
        deps: dict[str, tuple[str, ...]] = {
            "identify": ("identify",),
            "read_measurements": ("read_voltage", "read_current"),
            "set_voltage": ("set_voltage",),
            "set_current_limit": ("set_current_limit",),
            "configure_sas_table": ("sas_isc", "sas_imp", "sas_voc", "sas_vmp"),
            "output_on": ("output_on",),
            "output_off": ("output_off",),
            "apply_profile": ("sas_isc", "sas_imp", "sas_voc", "sas_vmp"),
            "safe_shutdown": ("output_off",),
        }
        templates: list[CommandTemplate] = []
        for t in STANDARD_TEMPLATES:
            t2 = CommandTemplate(**{**t.__dict__})
            required = deps.get(t.id, ())
            t2.verified = bool(required) and all(
                (_SCPI_MAP.get(d) or ScpiOp()).verified for d in required
            )
            templates.append(t2)

        return DriverCapabilities(
            model="Keysight E4360 (LAN SOCKET adapter)",
            driver_kind=self.driver_kind,
            simulation=False,
            firmware=self._firmware,
            max_voltage_v=self.soft_limits.get("max_voltage_v", 130.0),
            max_current_a=self.soft_limits.get("max_current_a", 20.0),
            supports_solar_array_table=True,
            command_templates=templates,
            capability_map_version=CAPABILITY_MAP_VERSION,
        )


def verification_report() -> list[dict[str, Any]]:
    """Machine-readable state of the fill-in table.

    Used by the commissioning script and the hardware-readiness screen.
    """
    return [
        {
            "op": op_id,
            "verified": op.verified,
            "has_write": op.write is not None,
            "has_query": op.query is not None,
            "has_readback": op.readback is not None,
            "note": op.note,
        }
        for op_id, op in _SCPI_MAP.items()
    ]
