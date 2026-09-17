#!/usr/bin/env python3
"""Probe an E4360 mainframe from this host and report which LAN paths answer.

    .venv/bin/python probe.py 10.1.20.126            # all checks
    .venv/bin/python probe.py 10.1.20.126 --reboot   # ...then SYST:REBoot over the first path that works

Checks, in order: plain TCP open on 5024 (telnet), 5025 (raw SCPI socket) and
111 (VXI-11 portmapper); then a real *IDN? over the raw socket and over VXI-11
using exactly the pyvisa code path the backend uses. Run it while the backend
is STOPPED and no telnet is open — otherwise you're measuring your own
sessions. Each probe opens one connection and closes it.
"""
import socket
import sys
import time

TIMEOUT = 3.0


def tcp_open(ip: str, port: int) -> str:
    t0 = time.perf_counter()
    try:
        with socket.create_connection((ip, port), timeout=TIMEOUT):
            return f"open   ({(time.perf_counter() - t0) * 1000:.0f} ms)"
    except socket.timeout:
        return "TIMEOUT (no answer — filtered, or instrument not accepting)"
    except OSError as e:
        return f"CLOSED ({e.strerror or e})"


def scpi(address: str) -> str:
    import pyvisa
    rm = pyvisa.ResourceManager("@py")
    t0 = time.perf_counter()
    inst = None
    try:
        inst = rm.open_resource(address, open_timeout=int(TIMEOUT * 1000), timeout=int(TIMEOUT * 1000),
                                read_termination="\n", write_termination="\n")
        idn = inst.query("*IDN?").strip()
        err = inst.query("SYST:ERR?").strip()
        return f"OK     ({(time.perf_counter() - t0) * 1000:.0f} ms)  {idn}   SYST:ERR? {err}"
    except Exception as e:
        return f"FAILED ({(time.perf_counter() - t0) * 1000:.0f} ms)  {type(e).__name__}: {str(e).strip()[:120]}"
    finally:
        if inst is not None:
            try:
                inst.close()
            except Exception:
                pass


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ip = sys.argv[1]
    reboot = "--reboot" in sys.argv
    print(f"probing {ip} from this host\n")
    for port, what in ((5024, "telnet SCPI (interactive)"), (5025, "raw SCPI socket"), (111, "VXI-11 portmapper")):
        print(f"  tcp {port:<5} {what:<26} {tcp_open(ip, port)}")
    print()
    paths = [("socket  TCPIP0::%s::5025::SOCKET", f"TCPIP0::{ip}::5025::SOCKET"),
             ("vxi11   TCPIP0::%s::inst0::INSTR", f"TCPIP0::{ip}::inst0::INSTR")]
    working = None
    for label, addr in paths:
        res = scpi(addr)
        print(f"  {label % ip:<44} {res}")
        if res.startswith("OK") and working is None:
            working = addr
    print()
    if working is None:
        print("no SCPI path answered. If the TCP ports are open but *IDN? fails, a session is still held\n"
              "(telnet window, another VISA client, a stale link). Free it, or power-cycle / SYST:REBoot the\n"
              "mainframe from its front panel or web page (http://%s)." % ip)
        sys.exit(2)
    print(f"use transport {'socket' if 'SOCKET' in working else 'vxi11'} for this unit in Configuration.")
    if reboot:
        print("\nsending SYST:REBoot (documented: returns the unit to its power-on state — output goes OFF)...")
        import pyvisa
        inst = pyvisa.ResourceManager("@py").open_resource(working, timeout=3000, read_termination="\n", write_termination="\n")
        inst.write("SYST:REB")
        try:
            inst.close()
        except Exception:
            pass
        print("sent. Allow ~30 s for the mainframe to come back, then re-run this probe.")


if __name__ == "__main__":
    main()
