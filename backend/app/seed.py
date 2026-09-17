"""One-time seed for a fresh (empty) database. Safe to call on every startup —
it's a no-op once any rack exists."""
import math
from datetime import datetime, timedelta, timezone

from . import orm
from .scpi import visa_address

ACTIVE_UNIT = "SAS-01"
STANDBY_UNIT = "SAS-02"


def _hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 997
    return h


def seed_if_empty(db):
    if db.query(orm.Rack).first():
        return  # already seeded

    rack = orm.Rack(id="A", name="RACK-A", loc="Lab 2 · Bay 1", cap=4)
    db.add(rack)

    # Both demo units address the bundled E4360 emulators (emulator.py) over
    # the raw-socket transport, so every command the app sends is real SCPI
    # parsed by a real (software) instrument. To drive the physical units,
    # repoint each row's IP at the real mainframe and switch the transport to
    # "vxi11" (the documented LAN interface) from Configuration → Simulator
    # Units. Their real MACs are kept below as labels. Everything under the
    # "mirrored" columns (online/output/mode/setpoints/readings) is populated
    # by the first poll — nothing is assumed about the instrument's state.
    db.add(orm.Unit(
        name=ACTIVE_UNIT, rack_id="A", slot=1, enabled=True, featured=True,
        ip_address="127.0.0.1", mac_address="80-09-02-05-6A-48", scpi_port=5025, transport="socket", channel=1,
        visa=visa_address("127.0.0.1", 5025, "socket"), poll_ms=1000, firmware="",
    ))
    db.add(orm.Unit(
        name=STANDBY_UNIT, rack_id="A", slot=2, enabled=True, featured=False,
        ip_address="127.0.0.1", mac_address="80-09-02-08-16-C4", scpi_port=5026, transport="socket", channel=1,
        visa=visa_address("127.0.0.1", 5026, "socket"), poll_ms=1000, firmware="",
    ))

    now = datetime.now(timezone.utc)

    # Backfill 24h of history so charts aren't empty on first run — clearly
    # synthetic rows at 5 min spacing; the poller appends real 1 s samples
    # from here forward.
    h = _hash(ACTIVE_UNIT)
    for i in range(24 * 12, 0, -1):
        ts = now - timedelta(minutes=5 * i)
        wobble = math.sin(i * 0.12 + h) * 1.4 + math.sin(i * 0.35) * 0.6
        v = round(28.0 + wobble * 0.05, 3)
        cur = round(4.2 + wobble * 0.08, 3)
        db.add(orm.Measurement(unit_name=ACTIVE_UNIT, ts=ts, reachable=True, voltage=v, current=cur,
                                power=round(v * cur, 3), quality="ok"))
        db.add(orm.Measurement(unit_name=STANDBY_UNIT, ts=ts, reachable=True, voltage=0.0, current=0.0,
                                power=0.0, quality="ok"))

    seed_alarms = [
        ("SAS-02", "SETPOINT_OK", "info", "Voltage setpoint applied within tolerance", False, 40),
        ("SAS-01", "PWR_NEAR_LIMIT", "warning", "Output power approaching configured limit (117.6 W of 160 W)", True, 3),
    ]
    for unit, code, sev, msg, active, mins_ago in seed_alarms:
        db.add(orm.AlarmRow(ts=now - timedelta(minutes=mins_ago), unit_name=unit, code=code,
                             sev=sev, msg=msg, active=active, ackd=False))

    run = orm.ScenarioRun(
        id="RUN-8836", scenario="Eclipse Cycle — Panel A", version="v1.3", status="Completed",
        dry=True, progress=100, targets=ACTIVE_UNIT, by="a.ng",
        started=(now - timedelta(hours=2)).strftime("%H:%M:%S"),
        finished=(now - timedelta(hours=2) + timedelta(minutes=2)).strftime("%H:%M:%S"),
        dur="2m 10s",
    )
    db.add(run)
    events = [
        ("start", "info", "Run accepted — scenario v1.3 approved · 1 target · correlation RUN-8836"),
        ("profile", "ok", "apply_profile BOL_GEO_28V → ACK"),
        ("setv", "ok", "set_voltage 28.0 V → ACK · readback verified"),
        ("enable", "ok", "output_on → completed"),
        ("read", "ok", "read_measurements → 28.002 V · 4.198 A · 117.55 W"),
        ("end", "ok", "Run completed — dry run, no hazardous commands dispatched"),
    ]
    base = now - timedelta(hours=2)
    for idx, (node, lvl, msg) in enumerate(events):
        db.add(orm.ScenarioRunEvent(run_id=run.id, t=(base + timedelta(seconds=idx * 20)).strftime("%H:%M:%S"),
                                     node=node, lvl=lvl, m=msg))

    db.commit()
