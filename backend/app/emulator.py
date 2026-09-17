"""A software E4360 mainframe that speaks the documented SCPI subset over a
raw TCP socket, so the real driver (scpi.py) can be exercised end to end with
no hardware attached. It is deliberately an *emulator*, not a stub: the same
bytes the driver would send to a physical unit are parsed here according to
the Programmer's Reference Guide — channel lists, implied header paths in
compound messages, long/short mnemonics, `*OPC?`, the `SYST:ERR?` FIFO with
the guide's own error codes — and the same response formats come back.

What it models, per channel: FIXed mode (rectangular I-V, CV/CC crossover
against a resistive load), SAS mode (the exponential Voc/Isc/Vmp/Imp model),
OVP/OCP latching into STAT:QUES:COND bits, and the *RST state table.
Anything not in the guide's command summary answers -113 "Undefined header".
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import re
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Output module ratings. MAX values match the guide's *RST table (VOC/ISC
# defaults = rated maximum): E4361A 65 V / 8.7 A, E4362A 130 V / 5.1 A.
MODULES = {
    "E4361A": {"vmax": 65.0, "imax": 8.7, "pmax": 510.0},
    "E4362A": {"vmax": 130.0, "imax": 5.1, "pmax": 600.0},
}

_LONG = {
    "SOURCE": "SOUR", "VOLTAGE": "VOLT", "CURRENT": "CURR", "LEVEL": "LEV", "IMMEDIATE": "IMM",
    "AMPLITUDE": "AMPL", "PROTECTION": "PROT", "OUTPUT": "OUTP", "STATE": "STAT", "CLEAR": "CLE",
    "MEASURE": "MEAS", "SCALAR": "SCAL", "FETCH": "FETC", "SYSTEM": "SYST", "ERROR": "ERR",
    "CHANNEL": "CHAN", "COUNT": "COUN", "MODEL": "MOD", "SERIAL": "SER", "OPTION": "OPT",
    "COMMUNICATE": "COMM", "RLSTATE": "RLST", "VERSION": "VERS", "STATUS": "STAT",
    "QUESTIONABLE": "QUES", "CONDITION": "COND", "OPERATION": "OPER", "EVENT": "EVEN",
    "POWER": "POW", "LIMIT": "LIM", "DISPLAY": "DISP", "WINDOW": "WIND", "TEXT": "TEXT", "ENABLE": "ENAB",
}
_OPTIONAL = {"SOUR", "LEV", "IMM", "AMPL", "SCAL", "DC", "WIND"}
_CHANLIST = re.compile(r"\(@([^)]*)\)")


@dataclass
class Channel:
    model: str
    serial: str
    load_ohms: float = 28.0 / 4.2       # resistive test load: 28 V -> 4.2 A -> 117.6 W
    mode: str = "FIX"
    volt: float = 0.0
    curr: float = 0.0
    ovp: float = 0.0
    ocp: float = 0.0
    output: bool = False
    output_before_fault: bool = False
    sas: dict = field(default_factory=dict)
    sas_mode: str = "IMM"
    ques: int = 0
    last_v: float | None = None
    last_i: float | None = None

    @property
    def rating(self) -> dict:
        return MODULES[self.model]

    def reset(self):
        r = self.rating
        self.mode, self.volt, self.curr = "FIX", 0.0, 0.0
        self.ovp, self.ocp = r["vmax"], 1.1 * r["imax"]
        self.output = self.output_before_fault = False
        self.sas = {"isc": r["imax"], "imp": 0.8 * r["imax"], "vmp": 0.8 * r["vmax"], "voc": r["vmax"]}
        self.sas_mode, self.ques = "IMM", 0
        self.last_v = self.last_i = None


class E4360Emulator:
    def __init__(self, port: int, channels: list[Channel], serial: str = "MY00000001", firmware: str = "A.02.05"):
        self.port = port
        self.channels = channels
        self.serial = serial
        self.firmware = firmware
        self.errors: deque[tuple[int, str]] = deque()
        self.rlstate = "LOC"
        for ch in channels:
            ch.reset()

    # ---------- error queue ----------
    def push_error(self, code: int, msg: str):
        if len(self.errors) >= 20:
            self.errors.pop()
            self.errors.append((-350, "Error queue overflow"))
            return
        self.errors.append((code, msg))

    # ---------- physics ----------
    @staticmethod
    def _sas_current(v: float, p: dict) -> float:
        isc, imp, vmp, voc = p["isc"], p["imp"], p["vmp"], p["voc"]
        if v >= voc:
            return 0.0
        c2 = (vmp / voc - 1.0) / math.log(1.0 - imp / isc)
        c1 = (1.0 - imp / isc) * math.exp(-vmp / (c2 * voc))
        return max(0.0, isc * (1.0 - c1 * (math.exp(v / (c2 * voc)) - 1.0)))

    def _operating_point(self, ch: Channel) -> tuple[float, float]:
        if not ch.output:
            return 0.0, 0.0
        r = ch.load_ohms
        if ch.mode == "FIX":
            v, i = ch.volt, ch.volt / r
            if i > ch.curr:            # constant-current crossover
                i, v = ch.curr, ch.curr * r
        else:
            lo, hi = 0.0, ch.sas["voc"]
            for _ in range(60):        # bisection: curve current == load-line current
                mid = (lo + hi) / 2
                if self._sas_current(mid, ch.sas) > mid / r:
                    lo = mid
                else:
                    hi = mid
            v = (lo + hi) / 2
            i = v / r
        if v * i > ch.rating["pmax"]:
            i = ch.rating["pmax"] / v if v else 0.0
        if v > ch.ovp:
            self._trip(ch, 1)
            return 0.0, 0.0
        if i > ch.ocp:
            self._trip(ch, 2)
            return 0.0, 0.0
        noise = 1 + random.uniform(-0.0004, 0.0004)
        return v * noise, i * noise

    def _trip(self, ch: Channel, bit: int):
        ch.output_before_fault = ch.output
        ch.output = False
        ch.ques |= bit

    def _measure(self, chans: list[Channel]):
        for ch in chans:
            ch.last_v, ch.last_i = self._operating_point(ch)

    # ---------- parsing ----------
    def _chanlist(self, args: str, is_query: bool) -> tuple[list[Channel] | None, str]:
        m = _CHANLIST.search(args)
        if not m:
            return [self.channels[0]], args.strip()
        if is_query and m.start() > 0 and args[m.start() - 1] not in " ,":
            self.push_error(-103, "Invalid separator")
            return None, ""
        idx: list[int] = []
        for part in m.group(1).split(","):
            part = part.strip()
            if ":" in part:
                a, b = part.split(":", 1)
                idx.extend(range(int(a), int(b) + 1))
            elif part:
                idx.append(int(part))
        if any(i < 1 or i > len(self.channels) for i in idx):
            self.push_error(100, "Too many channels")
            return None, ""
        rest = (args[:m.start()] + args[m.end():]).strip().rstrip(",").strip()
        return [self.channels[i - 1] for i in idx], rest

    def _number(self, tok: str, lo: float, hi: float) -> float | None:
        t = tok.strip().upper()
        if t in ("MAX", "MAXIMUM"):
            return hi
        if t in ("MIN", "MINIMUM"):
            return lo
        try:
            val = float(t)
        except ValueError:
            self.push_error(-104, "Data type error")
            return None
        if val < lo or val > hi:
            self.push_error(-222, "Data out of range")
            return None
        return val

    @staticmethod
    def _canonical(header: str) -> str:
        toks = [_LONG.get(t, t) for t in header.upper().split(":") if t]
        out: list[str] = []
        for i, t in enumerate(toks):
            if t in _OPTIONAL:
                continue
            if t == "STAT" and out and out[-1] == "OUTP":   # OUTPut[:STATe]
                continue
            out.append(t)
        return ":".join(out)

    @staticmethod
    def _nr3(v: float) -> str:
        return f"{v:+.6E}"

    def process_message(self, message: str) -> str | None:
        units = [u for u in message.strip().split(";") if u.strip()]
        responses: list[str] = []
        header_path = ""
        pending_sas: dict[int, dict] = {}
        for raw in units:
            raw = raw.strip()
            header, _, args = raw.partition(" ")
            if "(@" in header:                        # query glued to its channel list
                self.push_error(-103, "Invalid separator")
                continue
            if raw.startswith("*"):
                full = header
            elif header.startswith(":") or not header_path:
                full = header.lstrip(":")
                header_path = ":".join(full.rstrip("?").split(":")[:-1])
            else:
                full = f"{header_path}:{header}"
                header_path = ":".join(full.rstrip("?").split(":")[:-1])
            is_query = full.endswith("?")
            canon = self._canonical(full.rstrip("?"))
            resp = self._dispatch(canon, is_query, args.strip(), pending_sas)
            if is_query and resp is not None:
                responses.append(resp)
        for chan_idx, params in pending_sas.items():
            self._commit_sas(self.channels[chan_idx], params)
        return ";".join(responses) if responses else None

    def _commit_sas(self, ch: Channel, new: dict):
        p = {**ch.sas, **new}
        r = ch.rating
        if p["voc"] > r["vmax"]:
            self.push_error(328, "Calculated open circuit voltage too large"); return
        if p["isc"] > r["imax"] or p["imp"] > r["imax"]:
            self.push_error(-222, "Data out of range"); return
        if p["vmp"] >= p["voc"]:
            self.push_error(320, "VMP must be less than VOC"); return
        if p["imp"] > p["isc"]:
            self.push_error(321, "IMP must be less than or equal to ISC"); return
        if p["vmp"] <= 0.02 * r["vmax"] or p["imp"] <= 0.02 * r["imax"]:
            self.push_error(322, "VMP and/or IMP too small"); return
        ch.sas = p

    # ---------- command table ----------
    def _dispatch(self, canon: str, q: bool, args: str, pending_sas: dict) -> str | None:
        # --- IEEE-488.2 common commands ---
        if canon == "*IDN" and q:
            return f"KEYSIGHT TECHNOLOGIES,E4360A,{self.serial},{self.firmware}"
        if canon == "*RST":
            for ch in self.channels:
                ch.reset()
            return None
        if canon == "*CLS":
            self.errors.clear(); return None
        if canon == "*OPC":
            return "1" if q else None
        if canon in ("*WAI", "*TRG"):
            return None
        if canon in ("*ESR", "*STB", "*TST", "*OPT") and q:
            return "0"

        chans, rest = self._chanlist(args, q)
        if chans is None:
            return None
        ch0 = chans[0]

        # --- SYSTem ---
        if canon == "SYST:ERR" and q:
            code, msg = self.errors.popleft() if self.errors else (0, "No error")
            return f'{code:+d},"{msg}"'
        if canon == "SYST:CHAN" and q:
            return f"+{len(self.channels)}"
        if canon == "SYST:CHAN:MOD" and q:
            return ",".join(c.model for c in chans)
        if canon == "SYST:CHAN:SER" and q:
            return ";".join(c.serial for c in chans)
        if canon == "SYST:CHAN:OPT" and q:
            return ",".join('""' for _ in chans)
        if canon == "SYST:VERS" and q:
            return "1999.0"
        if canon == "SYST:COMM:RLST":
            if q:
                return self.rlstate
            v = rest.upper()[:3]
            if v not in ("LOC", "REM", "RWL"):
                self.push_error(-141, "Invalid character data"); return None
            self.rlstate = v
            return None

        # --- MEASure / FETCh ---
        if canon in ("MEAS:VOLT", "MEAS:CURR") and q:
            self._measure(chans)
            return ",".join(self._nr3(c.last_v if canon.endswith("VOLT") else c.last_i) for c in chans)
        if canon in ("FETC:VOLT", "FETC:CURR") and q:
            if any(c.last_v is None for c in chans):
                self.push_error(303, "There is not a valid acquisition to fetch from"); return None
            return ",".join(self._nr3(c.last_v if canon.endswith("VOLT") else c.last_i) for c in chans)

        # --- OUTPut ---
        if canon == "OUTP":
            if q:
                return ",".join("1" if c.output else "0" for c in chans)
            v = rest.upper()
            if v not in ("ON", "OFF", "1", "0"):
                self.push_error(-104, "Data type error"); return None
            on = v in ("ON", "1")
            for c in chans:
                c.output = on and not (c.ques & 0x13)   # latched OV/OC/OT keep the output down until PROT:CLE
            return None
        if canon == "OUTP:PROT:CLE" and not q:
            for c in chans:
                c.ques &= ~0x13
                c.output = c.output_before_fault
            return None

        # --- SOURce levels (FIXed mode only) ---
        if canon in ("VOLT", "CURR"):
            attr, hi = ("volt", ch0.rating["vmax"]) if canon == "VOLT" else ("curr", ch0.rating["imax"])
            if q:
                sel = rest.upper()
                if sel in ("MAX", "MAXIMUM"):
                    return ",".join(self._nr3(c.rating["vmax" if attr == "volt" else "imax"]) for c in chans)
                if sel in ("MIN", "MINIMUM"):
                    return ",".join(self._nr3(0.0) for _ in chans)
                return ",".join(self._nr3(getattr(c, attr)) for c in chans)
            if not rest:
                self.push_error(-109, "Missing parameter"); return None
            if any(c.mode != "FIX" for c in chans):
                self.push_error(315, "Settings conflict error"); return None
            val = self._number(rest, 0.0, hi)
            if val is None:
                return None
            for c in chans:
                setattr(c, attr, val)
            return None
        if canon in ("VOLT:PROT", "CURR:PROT"):
            attr, hi = ("ovp", ch0.rating["vmax"]) if canon == "VOLT:PROT" else ("ocp", 1.25 * ch0.rating["imax"])
            if q:
                return ",".join(self._nr3(getattr(c, attr)) for c in chans)
            if not rest:
                self.push_error(-109, "Missing parameter"); return None
            val = self._number(rest, 0.0, hi)
            if val is None:
                return None
            for c in chans:
                setattr(c, attr, val)
            return None

        # --- operating mode / SAS curve ---
        if canon == "CURR:MODE":
            if q:
                return ",".join(c.mode for c in chans)
            m = rest.upper()
            if m in ("FIX", "FIXED"):
                m = "FIX"
            elif m == "SAS":
                m = "SAS"
            elif m in ("TABL", "TABLE"):
                self.push_error(326, "Table not found"); return None
            else:
                self.push_error(-141, "Invalid character data"); return None
            for c in chans:
                c.mode = m
            return None
        if canon == "CURR:SAS:MODE":
            if q:
                return ",".join(c.sas_mode for c in chans)
            m = rest.upper()[:3]
            if m not in ("IMM", "LIS"):
                self.push_error(-141, "Invalid character data"); return None
            for c in chans:
                c.sas_mode = "IMM" if m == "IMM" else "LIST"
            return None
        sas_key = {"CURR:SAS:ISC": "isc", "CURR:SAS:IMP": "imp", "VOLT:SAS:VMP": "vmp", "VOLT:SAS:VOC": "voc"}.get(canon)
        if sas_key:
            if q:
                return ",".join(self._nr3(c.sas[sas_key]) for c in chans)
            if not rest:
                self.push_error(-109, "Missing parameter"); return None
            try:
                val = float(rest)
            except ValueError:
                self.push_error(-104, "Data type error"); return None
            for c in chans:
                pending_sas.setdefault(self.channels.index(c), {})[sas_key] = val
            return None

        # --- STATus ---
        if canon in ("STAT:QUES:COND", "STAT:QUES", "STAT:QUES:EVEN") and q:
            return ",".join(f"+{c.ques}" for c in chans)
        if canon in ("STAT:OPER:COND", "STAT:OPER", "STAT:OPER:EVEN") and q:
            return ",".join("+0" for _ in chans)
        if canon == "POW:LIM" and q:
            return ",".join(self._nr3(c.rating["pmax"]) for c in chans)
        if canon in ("DISP:TEXT", "DISP:ENAB", "DISP:VIEW") and not q:
            return None

        self.push_error(-113, "Undefined header")
        return None

    # ---------- server ----------
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                message = line.decode("ascii", "replace").strip("\r\n")
                if not message.strip():
                    continue
                response = self.process_message(message)
                if response is not None:
                    writer.write((response + "\n").encode("ascii", "replace"))
                    await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()

    async def serve(self, host: str = "127.0.0.1") -> asyncio.AbstractServer | None:
        try:
            return await asyncio.start_server(self._handle, host, self.port)
        except OSError:
            logger.warning("E4360 emulator could not bind %s:%s (port in use?)", host, self.port)
            return None


def demo_emulators() -> list[E4360Emulator]:
    """Two single-module E4361A mainframes. The first is left as an operator
    might have left it — 28 V / 5 A programmed, output on — so the demo has
    something to show; the second is at its *RST state."""
    active = E4360Emulator(5025, [Channel("E4361A", "MY00001001")], serial="MY00000001")
    ch = active.channels[0]
    ch.volt, ch.curr, ch.output = 28.0, 5.0, True
    standby = E4360Emulator(5026, [Channel("E4361A", "MY00001002")], serial="MY00000002")
    return [active, standby]
