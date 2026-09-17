"""Real SCPI driver for the Keysight Series E4360 Modular Solar Array Simulator.

Every mnemonic, parameter form, response format and error code used here is
taken from the Keysight "Series E4360 Programmer's Reference Guide"
(E4360-90902, Edition 3, Nov 2014 — `9018-03618.pdf` in the repo root):

  channel list   `(@<n>)` suffix on commands and queries. Optional (defaults to
                 channel 1). A query needs a space before it, otherwise the
                 instrument raises -103 "Invalid separator".
  terminator     <NL>
  completion     `*OPC?` returns 1 once all pending operations have finished —
                 output-state and level changes execute in parallel with the
                 next command, so this is how the guide's own example waits.
  error queue    `SYST:ERR?` -> `<NR1>,"<msg>"`, FIFO, `+0,"No error"` when
                 empty, cleared as read. Negative codes are command/syntax
                 errors, positive codes are device-dependent (e.g. 315 settings
                 conflict, 320/321/322 bad SAS curve, 329 exceeds soft limit).
  measurements   `MEAS:VOLT? (@n)` triggers a new acquisition of BOTH voltage
                 and current; `FETC:CURR? (@n)` returns the current from that
                 same acquisition without measuring again. Readings are <NR3>.
  transport      VISA `TCPIP0::<ip>::INSTR` (VXI-11), as in the guide's own
                 LAN example. A raw socket on a fixed port is NOT documented in
                 this guide; it is offered here as an opt-in transport for
                 users who have confirmed it on their instrument's LAN
                 configuration page, and for the bundled emulator.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import pyvisa
from pyvisa import constants

DEFAULT_TIMEOUT_MS = 2000
TRANSPORTS = ("vxi11", "socket")
MODES = {"FIX": "FIX", "FIXED": "FIX", "SAS": "SAS", "TABL": "TABL", "TABLE": "TABL"}

_rm: pyvisa.ResourceManager | None = None
_rm_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _resource_manager() -> pyvisa.ResourceManager:
    global _rm
    with _rm_guard:
        if _rm is None:
            _rm = pyvisa.ResourceManager("@py")  # pure-python backend: VXI-11 + raw socket, no NI/Keysight VISA needed
        return _rm


def _lock_for(address: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(address, threading.Lock())


def visa_address(ip_address: str, port: int, transport: str) -> str:
    if not ip_address:
        return ""
    if transport == "socket":
        return f"TCPIP0::{ip_address}::{port}::SOCKET"
    return f"TCPIP0::{ip_address}::inst0::INSTR"


def fmt(value: float) -> str:
    return format(float(value), ".6g")


@dataclass
class CommandResult:
    status: str                      # OK | ERR | UNREACHABLE | TIMEOUT
    sent: str
    response: str | None = None
    error_code: int | None = None
    error_msg: str | None = None
    latency_ms: int = 0
    readback_ok: bool = False

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    def describe(self) -> str:
        if self.status == "OK":
            return f"OK · {self.latency_ms} ms" + (f" · readback {self.response}" if self.response else "")
        if self.status == "ERR":
            return f"rejected by instrument · {self.error_code},\"{self.error_msg}\""
        return f"{self.status.lower()} · {self.error_msg or 'no response'}"


@dataclass
class Reading:
    voltage: float
    current: float
    output: bool
    mode: str                        # FIX | SAS | TABL
    questionable: int                # STAT:QUES:COND? bit field
    volt_set: float | None = None    # VOLT? — only meaningful in FIX mode
    curr_set: float | None = None    # CURR? — only meaningful in FIX mode
    extra: dict = field(default_factory=dict)

    @property
    def power(self) -> float:
        return round(self.voltage * self.current, 4)


class Instrument:
    """One output channel of one E4360 mainframe, addressed over LAN."""

    def __init__(self, ip_address: str, port: int, transport: str, channel: int = 1,
                 timeout_ms: int = DEFAULT_TIMEOUT_MS):
        self.address = visa_address(ip_address, port, transport)
        self.channel = int(channel or 1)
        self.timeout_ms = timeout_ms

    @classmethod
    def for_unit(cls, unit) -> "Instrument":
        return cls(unit.ip_address, unit.scpi_port, unit.transport, unit.channel)

    @property
    def ch(self) -> str:
        return f"(@{self.channel})"

    # ---------- transport ----------
    @contextmanager
    def _session(self):
        if not self.address:
            raise ConnectionError("no IP address configured")
        with _lock_for(self.address):
            inst = _resource_manager().open_resource(
                self.address, open_timeout=self.timeout_ms, timeout=self.timeout_ms,
                read_termination="\n", write_termination="\n",
            )
            try:
                yield inst
            finally:
                try:
                    inst.close()
                except Exception:
                    pass

    @staticmethod
    def _failure(sent: str, exc: Exception, t0: float) -> CommandResult:
        latency = int((time.perf_counter() - t0) * 1000)
        if isinstance(exc, pyvisa.errors.VisaIOError) and exc.error_code == constants.StatusCode.error_timeout:
            return CommandResult("TIMEOUT", sent, error_msg=f"no reply within {latency} ms", latency_ms=latency)
        msg = str(exc).strip() or exc.__class__.__name__
        return CommandResult("UNREACHABLE", sent, error_msg=msg[:160], latency_ms=latency)

    @staticmethod
    def _parse_error(raw: str) -> tuple[int, str]:
        code_s, _, msg = raw.strip().partition(",")
        try:
            code = int(float(code_s))
        except ValueError:
            code = -1
        return code, msg.strip().strip('"')

    def _drain_errors(self, inst) -> tuple[int, str]:
        """Read the FIFO until +0; report the FIRST error (the one that caused it)."""
        first: tuple[int, str] | None = None
        for _ in range(25):
            code, msg = self._parse_error(inst.query("SYST:ERR?"))
            if code == 0:
                break
            if first is None:
                first = (code, msg)
        return first or (0, "No error")

    @staticmethod
    def _readback_matches(response: str | None, expect) -> bool:
        if expect is None or response is None:
            return response is not None
        r = response.strip()
        if isinstance(expect, bool):
            return r in ("1", "ON") if expect else r in ("0", "OFF")
        if isinstance(expect, (int, float)):
            try:
                got = float(r.split(",")[0])
            except ValueError:
                return False
            return abs(got - float(expect)) <= max(0.005 * abs(float(expect)), 0.01)
        return r.upper().startswith(str(expect).upper()[:3])

    def _exec(self, inst, sent: str, readback: str | None = None, expect=None) -> CommandResult:
        t0 = time.perf_counter()
        inst.write(sent)
        inst.query("*OPC?")
        code, msg = self._drain_errors(inst)
        if code != 0:
            return CommandResult("ERR", sent, error_code=code, error_msg=msg,
                                 latency_ms=int((time.perf_counter() - t0) * 1000))
        response = inst.query(readback).strip() if readback else None
        return CommandResult("OK", sent, response=response, latency_ms=int((time.perf_counter() - t0) * 1000),
                             readback_ok=self._readback_matches(response, expect))

    def execute(self, sent: str, readback: str | None = None, expect=None) -> CommandResult:
        t0 = time.perf_counter()
        try:
            with self._session() as inst:
                return self._exec(inst, sent, readback, expect)
        except Exception as exc:  # VisaIOError, OSError, ConnectionError — all mean "didn't get through"
            return self._failure(sent, exc, t0)

    def query(self, sent: str) -> CommandResult:
        t0 = time.perf_counter()
        try:
            with self._session() as inst:
                response = inst.query(sent).strip()
                code, msg = self._drain_errors(inst)
                if code != 0:
                    return CommandResult("ERR", sent, response=response, error_code=code, error_msg=msg,
                                         latency_ms=int((time.perf_counter() - t0) * 1000))
                return CommandResult("OK", sent, response=response, latency_ms=int((time.perf_counter() - t0) * 1000),
                                     readback_ok=True)
        except Exception as exc:
            return self._failure(sent, exc, t0)

    # ---------- documented operations ----------
    def identify(self) -> CommandResult:
        res = self.query("*IDN?")
        if not res.ok:
            return res
        model = self.query(f"SYST:CHAN:MOD? {self.ch}")
        if model.ok:
            res.response = f"{res.response} · ch{self.channel} {model.response}"
            res.sent = f"*IDN?;SYST:CHAN:MOD? {self.ch}"
        return res

    def set_voltage(self, volts: float) -> CommandResult:
        """[SOURce:]VOLTage — FIXed mode only (the instrument answers 315 in SAS/TABLe mode)."""
        return self.execute(f"VOLT {fmt(volts)},{self.ch}", f"VOLT? {self.ch}", volts)

    def set_current(self, amps: float) -> CommandResult:
        return self.execute(f"CURR {fmt(amps)},{self.ch}", f"CURR? {self.ch}", amps)

    def set_output(self, on: bool) -> CommandResult:
        return self.execute(f"OUTP {'ON' if on else 'OFF'},{self.ch}", f"OUTP? {self.ch}", bool(on))

    def set_ovp(self, volts: float) -> CommandResult:
        return self.execute(f"VOLT:PROT {fmt(volts)},{self.ch}", f"VOLT:PROT? {self.ch}", volts)

    def set_ocp(self, amps: float) -> CommandResult:
        return self.execute(f"CURR:PROT:LEV {fmt(amps)},{self.ch}", f"CURR:PROT:LEV? {self.ch}", amps)

    def clear_protection(self) -> CommandResult:
        return self.execute(f"OUTP:PROT:CLE {self.ch}", f"STAT:QUES:COND? {self.ch}")

    def set_mode(self, mode: str) -> CommandResult:
        m = MODES.get(mode.upper())
        if not m:
            return CommandResult("ERR", f"CURR:MODE {mode}", error_code=-224, error_msg="Illegal parameter value")
        return self.execute(f"CURR:MODE {m},{self.ch}", f"CURR:MODE? {self.ch}", m)

    def apply_sas_curve(self, isc: float, imp: float, vmp: float, voc: float) -> CommandResult:
        """All four coupled curve parameters in ONE message, as the guide recommends,
        so the instrument validates the whole curve and rejects it atomically
        (320 VMP<VOC, 321 IMP<=ISC, 322 too small, 328 Voc exceeds rating)."""
        sent = (f"CURR:SAS:ISC {fmt(isc)},{self.ch};IMP {fmt(imp)},{self.ch};"
                f":VOLT:SAS:VMP {fmt(vmp)},{self.ch};VOC {fmt(voc)},{self.ch}")
        return self.execute(sent, f"VOLT:SAS:VOC? {self.ch}", voc)

    def safe_shutdown(self) -> CommandResult:
        return self.set_output(False)

    def measure(self) -> tuple[CommandResult, Reading | None]:
        """One round trip for the live picture of the channel: a fresh V/I
        acquisition plus output state, operating mode and protection status.
        Setpoints are read in a second round trip only in FIXed mode, where
        VOLT?/CURR? are meaningful."""
        compound = (f"MEAS:VOLT? {self.ch};:FETC:CURR? {self.ch};:OUTP? {self.ch};"
                    f":CURR:MODE? {self.ch};:STAT:QUES:COND? {self.ch}")
        t0 = time.perf_counter()
        try:
            with self._session() as inst:
                raw = inst.query(compound).strip()
                parts = [p.strip() for p in raw.split(";")]
                if len(parts) != 5:  # instrument didn't honour the compound query — fall back to one at a time
                    parts = [inst.query(q).strip() for q in (
                        f"MEAS:VOLT? {self.ch}", f"FETC:CURR? {self.ch}", f"OUTP? {self.ch}",
                        f"CURR:MODE? {self.ch}", f"STAT:QUES:COND? {self.ch}")]
                code, msg = self._drain_errors(inst)
                if code != 0:
                    return CommandResult("ERR", compound, response=raw, error_code=code, error_msg=msg,
                                         latency_ms=int((time.perf_counter() - t0) * 1000)), None
                reading = Reading(
                    voltage=float(parts[0]), current=float(parts[1]),
                    output=parts[2] in ("1", "ON"), mode=MODES.get(parts[3].upper(), parts[3].upper()[:4]),
                    questionable=int(float(parts[4])),
                )
                if reading.mode == "FIX":
                    sp = inst.query(f"VOLT? {self.ch};:CURR? {self.ch}").strip().split(";")
                    if len(sp) == 2:
                        reading.volt_set, reading.curr_set = float(sp[0]), float(sp[1])
                return CommandResult("OK", compound, response=raw, latency_ms=int((time.perf_counter() - t0) * 1000),
                                     readback_ok=True), reading
        except Exception as exc:
            return self._failure(compound, exc, t0), None


# STAT:QUES:COND? bit definitions (guide, "STATus:QUEStionable:CONDition?")
QUESTIONABLE_BITS = [
    (1, "OV", "critical", "Output disabled by over-voltage protection"),
    (2, "OC", "critical", "Output disabled by over-current protection"),
    (4, "PF", "critical", "Output disabled by power-fail (low AC line / brownout)"),
    (16, "OT", "critical", "Over-temperature protection tripped"),
    (256, "OS", "warning", "Over-switching protection tripped (>50 kHz)"),
    (512, "INH", "warning", "Output inhibited by external signal"),
    (1024, "UNR", "warning", "Output is unregulated"),
    (2048, "PROT", "warning", "Output disabled — coupled to a protection fault on another channel"),
]
