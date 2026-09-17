"""One-time seed for a fresh (empty) database, from a fleet file. Safe to call
on every startup — it's a no-op once any rack exists.

The fleet file (default `backend/fleet.json`, override with SAS_FLEET_FILE)
describes racks and units. Ship one per deployment: the committed
`fleet.json` addresses the lab's real E4360 mainframes; `fleet.emulator.json`
addresses the bundled emulators for a no-hardware demo:

    SAS_FLEET_FILE=fleet.emulator.json .venv/bin/python -m uvicorn app.main:app ...
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import orm
from .scpi import visa_address

BACKEND_DIR = Path(__file__).resolve().parent.parent
FLEET_FILE = Path(os.environ.get("SAS_FLEET_FILE", BACKEND_DIR / "fleet.json"))
if not FLEET_FILE.is_absolute():
    FLEET_FILE = BACKEND_DIR / FLEET_FILE


def load_fleet() -> dict:
    path = FLEET_FILE if FLEET_FILE.exists() else BACKEND_DIR / "fleet.emulator.json"
    return json.loads(path.read_text())


def is_loopback(ip: str) -> bool:
    return ip.startswith("127.") or ip in ("localhost", "::1")


def apply_fleet(db) -> dict:
    """Re-apply the fleet file to an EXISTING database: re-address units that
    are already there (matched by name), add ones that are missing, leave
    everything else — measurements, history, alarms, extra units — alone.

    This is the bridge for a database seeded before the fleet file existed (or
    from a different one): `seed_if_empty` only runs on an empty database, so
    pulling a new fleet.json otherwise has no effect on units already stored.
    """
    from .scpi import close_session

    fleet = load_fleet()
    for r in fleet["racks"]:
        rack = db.get(orm.Rack, r["id"])
        if rack is None:
            db.add(orm.Rack(id=r["id"], name=r["name"], loc=r.get("loc", ""), cap=int(r.get("cap", 4))))

    added, readdressed, unchanged = [], [], []
    for spec in fleet["units"]:
        ip, port = spec.get("ip", ""), int(spec.get("port", 5025))
        transport, channel = spec.get("transport", "auto"), int(spec.get("channel", 1))
        u = db.get(orm.Unit, spec["name"])
        if u is None:
            db.add(orm.Unit(
                name=spec["name"], rack_id=spec["rack"], slot=int(spec["slot"]), enabled=spec.get("enabled", True),
                featured=bool(spec.get("featured", False)), ip_address=ip, mac_address=spec.get("mac", ""),
                scpi_port=port, transport=transport, channel=channel, visa=visa_address(ip, port, transport),
                poll_ms=1000, firmware="",
            ))
            added.append(spec["name"])
            continue
        if (u.ip_address, u.scpi_port, u.transport, u.channel) == (ip, port, transport, channel):
            unchanged.append(u.name)
            continue
        close_session(u.visa)
        u.ip_address, u.scpi_port, u.transport, u.channel = ip, port, transport, channel
        u.mac_address = spec.get("mac", u.mac_address)
        u.visa = visa_address(ip, port, transport)
        u.online, u.firmware, u.op_mode = False, "", ""
        u.last_voltage = u.last_current = u.last_power = None
        u.last_error = "re-addressed from fleet file — awaiting first poll"
        readdressed.append(u.name)
    db.commit()
    return {"file": str(FLEET_FILE), "added": added, "readdressed": readdressed, "unchanged": unchanged}


def _hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 997
    return h


def seed_if_empty(db):
    if db.query(orm.Rack).first():
        return  # already seeded

    fleet = load_fleet()
    for r in fleet["racks"]:
        db.add(orm.Rack(id=r["id"], name=r["name"], loc=r.get("loc", ""), cap=int(r.get("cap", 4))))

    now = datetime.now(timezone.utc)
    for spec in fleet["units"]:
        ip = spec.get("ip", "")
        port = int(spec.get("port", 5025))
        transport = spec.get("transport", "auto")
        db.add(orm.Unit(
            name=spec["name"], rack_id=spec["rack"], slot=int(spec["slot"]), enabled=spec.get("enabled", True),
            featured=bool(spec.get("featured", False)),
            ip_address=ip, mac_address=spec.get("mac", ""), scpi_port=port, transport=transport,
            channel=int(spec.get("channel", 1)), visa=visa_address(ip, port, transport),
            poll_ms=1000, firmware="",
        ))
        # Emulated units get 24 h of clearly synthetic history so demo charts
        # aren't empty. Real instruments start with an empty history — every
        # sample they ever show was actually measured.
        if is_loopback(ip):
            h = _hash(spec["name"])
            active = bool(spec.get("featured"))
            for i in range(24 * 12, 0, -1):
                ts = now - timedelta(minutes=5 * i)
                wobble = math.sin(i * 0.12 + h) * 1.4 + math.sin(i * 0.35) * 0.6
                v = round(28.0 + wobble * 0.05, 3) if active else 0.0
                cur = round(4.2 + wobble * 0.08, 3) if active else 0.0
                db.add(orm.Measurement(unit_name=spec["name"], ts=ts, reachable=True, voltage=v, current=cur,
                                        power=round(v * cur, 3), quality="ok"))

    first = fleet["units"][0]["name"] if fleet["units"] else None
    if first and is_loopback(fleet["units"][0].get("ip", "")):
        # Demo dressing for the emulator fleet only.
        db.add(orm.AlarmRow(ts=now - timedelta(minutes=3), unit_name=first, code="PWR_NEAR_LIMIT", sev="warning",
                             msg="Output power approaching configured limit (117.6 W of 160 W)", active=True, ackd=False))
        run = orm.ScenarioRun(
            id="RUN-8836", scenario="Eclipse Cycle — Panel A", version="v1.3", status="Completed",
            dry=True, progress=100, targets=first, by="a.ng",
            started=(now - timedelta(hours=2)).strftime("%H:%M:%S"),
            finished=(now - timedelta(hours=2) + timedelta(minutes=2)).strftime("%H:%M:%S"), dur="2m 10s",
        )
        db.add(run)
        events = [
            ("start", "info", "Run accepted — scenario v1.3 approved · 1 target · correlation RUN-8836"),
            ("profile", "ok", "apply_profile BOL_GEO_28V → ACK"),
            ("enable", "ok", "output_on → completed"),
            ("read", "ok", "read_measurements → 28.002 V · 4.198 A · 117.55 W"),
            ("end", "ok", "Run completed — dry run, no hazardous commands dispatched"),
        ]
        base = now - timedelta(hours=2)
        for idx, (node, lvl, msg) in enumerate(events):
            db.add(orm.ScenarioRunEvent(run_id=run.id, t=(base + timedelta(seconds=idx * 20)).strftime("%H:%M:%S"),
                                         node=node, lvl=lvl, m=msg))

    db.commit()
