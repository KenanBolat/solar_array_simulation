"""Connectivity diagnostics run FROM THE BACKEND HOST — the only vantage point
that matters, since it's the backend that talks to the instruments. Each
check opens one connection and closes it."""
from __future__ import annotations

import socket
import time

TIMEOUT = 3.0


def host_addresses() -> dict:
    """Hostname and the LAN IPv4 addresses users can put in a browser instead
    of 0.0.0.0 / localhost."""
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packet is sent; picks the default-route interface
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return {"hostname": socket.gethostname(), "ips": ips}


def _tcp(ip: str, port: int) -> tuple[bool, str]:
    t0 = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=TIMEOUT):
            return True, f"open · {(time.perf_counter() - t0) * 1000:.0f} ms"
    except socket.timeout:
        return False, "timeout — no answer (filtered, wrong IP, or instrument not accepting)"
    except OSError as e:
        return False, f"closed · {e.strerror or e}"


def _scpi(address: str, channel: int) -> tuple[bool, str]:
    import pyvisa
    t0 = time.perf_counter()
    inst = None
    try:
        inst = pyvisa.ResourceManager("@py").open_resource(
            address, open_timeout=int(TIMEOUT * 1000), timeout=int(TIMEOUT * 1000),
            read_termination="\n", write_termination="\n")
        idn = inst.query("*IDN?").strip()
        model = inst.query(f"SYST:CHAN:MOD? (@{channel})").strip()
        err = inst.query("SYST:ERR?").strip()
        return True, f"{idn} · ch{channel} {model} · SYST:ERR? {err} · {(time.perf_counter() - t0) * 1000:.0f} ms"
    except Exception as e:
        from .scpi import Instrument
        msg = Instrument._humanise(str(e).strip() or type(e).__name__)
        return False, f"{msg[:140]} · {(time.perf_counter() - t0) * 1000:.0f} ms"
    finally:
        if inst is not None:
            try:
                inst.close()
            except Exception:
                pass


def diagnose(ip: str, port: int, channel: int) -> dict:
    checks = []
    if not ip:
        return {"checks": [{"check": "address", "ok": False, "detail": "no IP configured"}], "recommend": None}
    for p, what in ((5024, "tcp 5024 · telnet SCPI"), (port, f"tcp {port} · raw SCPI socket"), (111, "tcp 111 · VXI-11 portmapper")):
        ok, detail = _tcp(ip, p)
        checks.append({"check": what, "ok": ok, "detail": detail})
    recommend = None
    ok, detail = _scpi(f"TCPIP0::{ip}::inst0::INSTR", channel)
    checks.append({"check": "*IDN? over VXI-11", "ok": ok, "detail": detail})
    if ok:
        recommend = "vxi11"
    ok, detail = _scpi(f"TCPIP0::{ip}::{port}::SOCKET", channel)
    checks.append({"check": f"*IDN? over socket :{port}", "ok": ok, "detail": detail})
    if ok and recommend is None:
        recommend = "socket"
    verdict = (f"instrument answers — use transport {recommend}" if recommend else
               ("ports open but no SCPI reply — a session is still held (telnet / another client / stale link): "
                "close it, or Reboot the mainframe" if any(c["ok"] for c in checks[:3]) else
                "nothing answers at this IP from this host — check IP, cabling, subnet/VLAN and the instrument's LAN page"))
    return {"checks": checks, "recommend": recommend, "verdict": verdict}
