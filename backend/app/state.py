import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import data, orm
from .db import session_scope
from .scpi import QUESTIONABLE_BITS, CommandResult, Reading, visa_address

MODE_LABEL = {"FIX": "FIXED", "SAS": "SAS CURVE", "TABL": "TABLE"}
PROTECTION_MASK = sum(bit for bit, *_ in QUESTIONABLE_BITS)

RANGE_WINDOW = {
    "5 min": timedelta(minutes=5),
    "30 min": timedelta(minutes=30),
    "1 hour": timedelta(hours=1),
    "24 hours": timedelta(hours=24),
    "Custom": timedelta(minutes=30),
}

_run_tasks: dict[str, asyncio.Task] = {}


def now_hhmmss():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


# ---------- units ----------
def unit_live_values(u: orm.Unit):
    """Last reading the poller mirrored from the instrument. (None, None, None)
    means no valid reply — never a computed stand-in."""
    if not (u.enabled and u.online):
        return None, None, None
    return u.last_voltage, u.last_current, u.last_power


def unit_status(u: orm.Unit):
    if not u.enabled or not u.online:
        return "OFFLINE", "faint"
    if u.alarm == "warning":
        return "WARNING", "amber"
    if u.output:
        return "ACTIVE", "cyan"
    return "ONLINE", "green"


def unit_to_dict(u: orm.Unit):
    v, i, p = unit_live_values(u)
    status_text, status_color = unit_status(u)
    return {
        "name": u.name, "rack": u.rack_id, "slot": u.slot,
        "pos": f"{u.rack.name} · S{u.slot}",
        "online": bool(u.enabled and u.online), "output": bool(u.output), "alarm": u.alarm,
        "statusText": status_text, "statusColor": status_color,
        "voltage": v, "current": i, "power": p,
        "voltageSetpoint": u.voltage_setpoint, "currentLimit": u.current_limit,
        "opMode": u.op_mode or None, "questionable": u.questionable,
        "channel": u.channel, "transport": u.transport,
        "featured": u.featured, "enabled": u.enabled,
    }


def _device_state(u: orm.Unit) -> str:
    if not (u.enabled and u.online):
        return "No comms"
    if u.questionable & PROTECTION_MASK:
        tripped = [code for bit, code, *_ in QUESTIONABLE_BITS if u.questionable & bit]
        return "Protection " + "/".join(tripped)
    return "Stable" if u.output else "Output Disabled"


def unit_to_detail_dict(u: orm.Unit):
    base = unit_to_dict(u)
    base.update({
        "connection": "CONNECTED" if (u.enabled and u.online) else "OFFLINE",
        "ipAddress": u.ip_address, "macAddress": u.mac_address, "scpiPort": u.scpi_port, "visa": u.visa,
        "lastComm": now_hhmmss() if (u.enabled and u.online) else "—",
        "firmware": u.firmware or "—",
        "mode": MODE_LABEL.get(u.op_mode, "—") if (u.enabled and u.online) else "—",
        "deviceState": _device_state(u),
    })
    return base


def apply_reading(db: Session, u: orm.Unit, result: CommandResult, reading: Reading | None):
    """Mirror one poll result into the unit row + one measurement row."""
    if result.ok and reading is not None:
        u.online = True
        u.last_voltage = round(reading.voltage, 4)
        u.last_current = round(reading.current, 4)
        u.last_power = round(reading.voltage * reading.current, 3)
        u.output = reading.output
        u.op_mode = reading.mode
        if reading.volt_set is not None:
            u.voltage_setpoint = reading.volt_set
        if reading.curr_set is not None:
            u.current_limit = reading.curr_set
        sync_protection_alarms(db, u, reading.questionable)
        record_measurement(db, u.name, u.last_voltage, u.last_current, u.last_power, reachable=True)
    else:
        u.online = False
        u.last_voltage = u.last_current = u.last_power = None
        record_measurement(db, u.name, None, None, None, reachable=False)


def sync_protection_alarms(db: Session, u: orm.Unit, questionable: int):
    """Raise an alarm row when a STAT:QUES:COND bit latches, retire it when it clears."""
    prev = u.questionable or 0
    u.questionable = questionable
    for bit, code, sev, msg in QUESTIONABLE_BITS:
        now_set, was_set = bool(questionable & bit), bool(prev & bit)
        if now_set and not was_set:
            db.add(orm.AlarmRow(ts=datetime.now(timezone.utc), unit_name=u.name, code=f"PROT_{code}",
                                 sev=sev, msg=msg, active=True, ackd=False))
        elif was_set and not now_set:
            for a in db.query(orm.AlarmRow).filter(orm.AlarmRow.unit_name == u.name,
                                                   orm.AlarmRow.code == f"PROT_{code}",
                                                   orm.AlarmRow.active.is_(True)).all():
                a.active = False
    u.alarm = "warning" if questionable & PROTECTION_MASK else "normal"


def derive_visa(ip_address: str, port: int = 5025, transport: str = "vxi11") -> str:
    return visa_address(ip_address, port, transport)


def describe_identity(idn_response: str) -> str:
    """'KEYSIGHT TECHNOLOGIES,E4360A,MY00000001,A.02.05 · ch1 E4361A' -> 'E4360A A.02.05 · ch1 E4361A'."""
    head, _, module = idn_response.partition(" · ")
    fields = [f.strip() for f in head.split(",")]
    compact = f"{fields[1]} {fields[3]}" if len(fields) >= 4 else head
    return f"{compact} · {module}" if module else compact


def get_unit(db: Session, name: str):
    return db.get(orm.Unit, name)


def list_units(db: Session):
    return db.query(orm.Unit).order_by(orm.Unit.rack_id, orm.Unit.slot).all()


def racks(db: Session):
    out = []
    for rack in db.query(orm.Rack).order_by(orm.Rack.id).all():
        us = sorted(rack.units, key=lambda u: u.slot)
        out.append({
            "id": rack.id, "name": rack.name, "loc": rack.loc, "cap": rack.cap,
            "count": len(us), "onCount": sum(1 for u in us if u.enabled and u.online),
            "units": [unit_to_dict(u) for u in us],
        })
    return out


def summary(db: Session):
    units = list_units(db)
    online = sum(1 for u in units if u.enabled and u.online)
    active_out = sum(1 for u in units if u.enabled and u.online and u.output)
    live_powers = [unit_live_values(u)[2] for u in units if u.enabled and u.online and u.output]
    total_p = sum(p for p in live_powers if p is not None)
    running = db.query(orm.ScenarioRun).filter(orm.ScenarioRun.status == "Running").count()
    active_alarms = db.query(orm.AlarmRow).filter(orm.AlarmRow.active.is_(True), orm.AlarmRow.ackd.is_(False)).count()
    crit_alarms = db.query(orm.AlarmRow).filter(orm.AlarmRow.active.is_(True), orm.AlarmRow.ackd.is_(False), orm.AlarmRow.sev == "critical").count()
    return {
        "configuredUnits": len(units), "onlineDevices": online, "activeOutputs": active_out,
        "totalPowerW": round(total_p, 1), "runningScenarios": running,
        "activeAlarms": active_alarms, "criticalAlarms": crit_alarms,
    }


def create_unit(db: Session, name: str, rack_id: str, ip_address: str = "", mac_address: str = "",
                 scpi_port: int = 5025, transport: str = "vxi11", channel: int = 1,
                 poll_ms: int = 1000, slot: int | None = None):
    rack = db.get(orm.Rack, rack_id)
    if not rack:
        raise ValueError(f"Unknown rack {rack_id}")
    taken = {u.slot for u in rack.units}
    if slot is None:
        slot = next((s for s in range(1, rack.cap + 1) if s not in taken), None)
        if slot is None:
            raise ValueError(f"Rack {rack_id} is at capacity ({rack.cap} slots)")
    elif slot in taken:
        raise ValueError(f"Slot {slot} in rack {rack_id} is already occupied")
    unit = orm.Unit(
        name=name, rack_id=rack_id, slot=slot, enabled=True, featured=False,
        ip_address=ip_address, mac_address=mac_address, scpi_port=scpi_port,
        transport=transport, channel=channel,
        visa=derive_visa(ip_address, scpi_port, transport), poll_ms=poll_ms, firmware="",
        online=False,  # unknown until the first poll gets a valid reply
    )
    db.add(unit)
    db.commit()
    return unit


def update_unit_network(db: Session, name: str, ip_address: str | None, mac_address: str | None,
                         scpi_port: int | None = None, transport: str | None = None,
                         channel: int | None = None):
    unit = db.get(orm.Unit, name)
    if not unit:
        return None
    if ip_address is not None:
        unit.ip_address = ip_address
    if mac_address is not None:
        unit.mac_address = mac_address
    if scpi_port is not None:
        unit.scpi_port = scpi_port
    if transport is not None:
        unit.transport = transport
    if channel is not None:
        unit.channel = channel
    unit.visa = derive_visa(unit.ip_address, unit.scpi_port, unit.transport)
    unit.online = False  # re-established by the next poll against the new address
    db.commit()
    return unit


def delete_unit(db: Session, name: str):
    unit = db.get(orm.Unit, name)
    if not unit:
        return False
    db.query(orm.Measurement).filter(orm.Measurement.unit_name == name).delete()
    db.delete(unit)
    db.commit()
    return True


def set_unit_enabled(db: Session, name: str, enabled: bool):
    unit = db.get(orm.Unit, name)
    if not unit:
        return None
    unit.enabled = enabled
    unit.online = False  # a disabled unit isn't polled; an enabled one is unknown until polled
    if not enabled:
        unit.last_voltage = unit.last_current = unit.last_power = None
    db.commit()
    return unit


# The instrument has already confirmed these (readback) by the time they're
# called — they just bring the cached row forward so the UI doesn't wait for
# the next poll.
def mirror_output(db: Session, name: str, on: bool):
    unit = db.get(orm.Unit, name)
    unit.output = on
    db.commit()
    return unit


def mirror_setpoint(db: Session, name: str, voltage: float | None = None, current_limit: float | None = None):
    unit = db.get(orm.Unit, name)
    if voltage is not None:
        unit.voltage_setpoint = voltage
    if current_limit is not None:
        unit.current_limit = current_limit
    db.commit()
    return unit


def mirror_mode(db: Session, name: str, mode: str):
    unit = db.get(orm.Unit, name)
    unit.op_mode = mode
    db.commit()
    return unit


# ---------- command / audit log ----------
def log_command(db: Session, user: str, dev: str, tpl: str, result: CommandResult):
    row = orm.CommandHistoryRow(
        ts=datetime.now(timezone.utc), user=user, device=dev, template=tpl,
        status=result.status, latency_ms=result.latency_ms, readback=result.readback_ok, correlation_id="",
        scpi=result.sent, response=result.response or "", error_code=result.error_code,
        error_msg=result.error_msg or "",
    )
    db.add(row)
    db.flush()
    row.correlation_id = "CMD-" + format(0x9F00 + row.id, "X")
    db.commit()
    return _history_row_dict(row)


def _history_row_dict(row: orm.CommandHistoryRow):
    return {
        "t": row.ts.strftime("%H:%M:%S"), "user": row.user, "dev": row.device, "tpl": row.template,
        "st": row.status, "lat": f"{row.latency_ms} ms", "rb": row.readback, "cid": row.correlation_id,
        "scpi": row.scpi, "resp": row.response, "errCode": row.error_code, "err": row.error_msg,
    }


def history_view(db: Session, flt: str, limit: int = 200):
    q = db.query(orm.CommandHistoryRow)
    if flt != "All":
        q = q.filter(orm.CommandHistoryRow.status == flt)
    total = q.count()
    rows = q.order_by(orm.CommandHistoryRow.ts.desc()).limit(limit).all()
    return {"rows": [_history_row_dict(r) for r in rows], "total": total, "shown": len(rows)}


# ---------- measurements ----------
def record_measurement(db: Session, unit_name: str, v: float | None, i: float | None, p: float | None, reachable: bool):
    quality = "ok" if reachable else "no_reading"
    db.add(orm.Measurement(unit_name=unit_name, ts=datetime.now(timezone.utc), reachable=reachable,
                            voltage=v, current=i, power=p, quality=quality))
    db.commit()


def telemetry(db: Session, unit_name: str, rng: str):
    window = RANGE_WINDOW.get(rng, RANGE_WINDOW["30 min"])
    since = datetime.now(timezone.utc) - window
    rows = (db.query(orm.Measurement)
            .filter(orm.Measurement.unit_name == unit_name, orm.Measurement.ts >= since)
            .order_by(orm.Measurement.ts.asc()).all())
    return {
        "t": rng, "n": len(rows),
        "v": [r.voltage for r in rows], "i": [r.current for r in rows], "p": [r.power for r in rows],
    }


def measurements(db: Session, unit_names: list[str], rng: str):
    window = RANGE_WINDOW.get(rng, RANGE_WINDOW["30 min"])
    since = datetime.now(timezone.utc) - window
    series = []
    rows_out = []
    for name in unit_names:
        u = get_unit(db, name)
        rows = (db.query(orm.Measurement)
                .filter(orm.Measurement.unit_name == name, orm.Measurement.ts >= since)
                .order_by(orm.Measurement.ts.asc()).all())
        _, color = unit_status(u) if u else (None, "cyan")
        series.append({
            "name": name, "statusColor": color,
            "v": [r.voltage for r in rows], "i": [r.current for r in rows], "p": [r.power for r in rows],
        })
        for r in reversed(rows[-3:]):
            rows_out.append({
                "unit": name, "time": r.ts.strftime("%H:%M:%S"),
                "v": round(r.voltage, 3) if r.voltage is not None else None,
                "i": round(r.current, 3) if r.current is not None else None,
                "p": round(r.power, 2) if r.power is not None else None,
                "out": "ON" if (u and u.output) else "OFF", "q": r.quality,
            })
    n = max((len(s["v"]) for s in series), default=0)
    return {"series": series, "rows": rows_out, "count": len(unit_names), "sampleText": f"{n} samples · {rng}"}


# ---------- alarms ----------
def _alarm_dict(a: orm.AlarmRow):
    return {"id": a.id, "time": a.ts.strftime("%H:%M:%S"), "unit": a.unit_name, "code": a.code,
            "sev": a.sev, "msg": a.msg, "active": a.active, "ackd": a.ackd}


def alarms_view(db: Session, flt: str):
    q = db.query(orm.AlarmRow)
    if flt == "Active":
        q = q.filter(orm.AlarmRow.active.is_(True))
    elif flt == "History":
        q = q.filter(orm.AlarmRow.active.is_(False))
    rows = q.order_by(orm.AlarmRow.ts.desc()).all()
    active_count = db.query(orm.AlarmRow).filter(orm.AlarmRow.active.is_(True)).count()
    crit_count = db.query(orm.AlarmRow).filter(orm.AlarmRow.active.is_(True), orm.AlarmRow.sev == "critical").count()
    return {"rows": [_alarm_dict(a) for a in rows], "activeCount": active_count, "critCount": crit_count}


def ack_alarm(db: Session, alarm_id: int):
    a = db.get(orm.AlarmRow, alarm_id)
    if not a:
        return None
    a.ackd = True
    db.commit()
    return _alarm_dict(a)


# ---------- scenario runs ----------
def _run_dict(r: orm.ScenarioRun):
    return {"id": r.id, "scenario": r.scenario, "version": r.version, "status": r.status,
            "dry": r.dry, "prog": r.progress, "targets": r.targets.split(",") if r.targets else [],
            "by": r.by, "started": r.started, "finished": r.finished, "dur": r.dur}


def runs_view(db: Session, flt: str):
    q = db.query(orm.ScenarioRun)
    if flt != "All":
        q = q.filter(orm.ScenarioRun.status == flt)
    return [_run_dict(r) for r in q.order_by(orm.ScenarioRun.started.desc()).all()]


def run_detail(db: Session, run_id: str):
    r = db.get(orm.ScenarioRun, run_id)
    if not r:
        return None
    d = _run_dict(r)
    events = (db.query(orm.ScenarioRunEvent).filter(orm.ScenarioRunEvent.run_id == run_id)
              .order_by(orm.ScenarioRunEvent.id.asc()).all())
    d["events"] = [{"t": e.t, "node": e.node, "lvl": e.lvl, "m": e.m} for e in events]
    return d


def create_run(db: Session, scenario: str, version: str, targets: list[str], by: str = "a.ng", dry: bool = False):
    count = db.query(orm.ScenarioRun).count()
    run_id = f"RUN-{8843 + count}"
    db.add(orm.ScenarioRun(id=run_id, scenario=scenario, version=version, status="Queued",
                            dry=dry, progress=0, targets=",".join(targets), by=by,
                            started=now_hhmmss(), finished="—", dur="0s"))
    db.commit()
    return run_id


async def start_run(run_id: str):
    with session_scope() as db:
        r = db.get(orm.ScenarioRun, run_id)
        if not r or r.status == "Running":
            return
        r.status, r.progress, r.finished = "Running", 0, "—"
        r.started = now_hhmmss()
        db.add(orm.ScenarioRunEvent(run_id=run_id, t=now_hhmmss(), node="start", lvl="info",
                                     m=f"Run accepted — scenario {r.version} approved · {len(r.targets.split(','))} target(s)"))

    steps = ["profile", "setv", "enable", "wait", "read", "thresh", "record", "disable", "end"]

    async def _drive():
        for idx, step in enumerate(steps):
            await asyncio.sleep(1.2)
            with session_scope() as db:
                r = db.get(orm.ScenarioRun, run_id)
                if not r or r.status != "Running":
                    return
                r.progress = round((idx + 1) / len(steps) * 100)
                db.add(orm.ScenarioRunEvent(run_id=run_id, t=now_hhmmss(), node=step, lvl="ok", m=f"{step} → completed"))
        with session_scope() as db:
            r = db.get(orm.ScenarioRun, run_id)
            if r and r.status == "Running":
                r.status, r.progress, r.finished = "Completed", 100, now_hhmmss()
                db.add(orm.ScenarioRunEvent(run_id=run_id, t=now_hhmmss(), node="end", lvl="ok", m="Run completed"))

    _run_tasks[run_id] = asyncio.create_task(_drive())


def pause_run(db: Session, run_id: str):
    r = db.get(orm.ScenarioRun, run_id)
    if r and r.status == "Running":
        return {"ok": True, "message": f"Pause requested · {run_id}"}
    return {"ok": False, "message": "Run is not active"}


def abort_run(db: Session, run_id: str):
    r = db.get(orm.ScenarioRun, run_id)
    if not r or r.status != "Running":
        return {"ok": False, "message": "Run is not active"}
    task = _run_tasks.pop(run_id, None)
    if task:
        task.cancel()
    r.status, r.finished = "Aborted", now_hhmmss()
    db.add(orm.ScenarioRunEvent(run_id=run_id, t=now_hhmmss(), node="shutdown", lvl="err",
                                 m="Abort dispatched · safe_shutdown on all targets"))
    db.commit()
    return {"ok": True, "message": f"Abort dispatched · {run_id}"}


# ---------- scenario builder (static demo graph, not persisted) ----------
def scenario_graph():
    nodes = [dict(n) for n in data.NODE_DEFS]
    edges = [{"from": a, "to": b, "kind": k, "fail": f} for a, b, k, f in data.EDGE_DEFS]
    return {"scenario": data.SCENARIO, "nodes": nodes, "edges": edges, "palette": data.NODE_PALETTE}


def node_props(node_id: str):
    if node_id in data.NODE_PROPS_OVERRIDE:
        return data.NODE_PROPS_OVERRIDE[node_id]
    n = next((n for n in data.NODE_DEFS if n["id"] == node_id), None)
    if not n:
        return None
    return {
        "name": n["label"], "target": "Scenario default group",
        "params": [["Type", n["type"]], ["Value", n.get("sub", "—")]],
        "delay": "0 ms", "timeout": "5 000 ms", "retry": "0 retries",
        "fail": "Abort scenario", "comments": "—",
    }


# ---------- configuration ----------
def config_units(db: Session):
    out = []
    for u in list_units(db):
        out.append({
            "name": u.name, "rack": u.rack.name, "slot": f"S{u.slot}",
            "ipAddress": u.ip_address, "macAddress": u.mac_address, "scpiPort": u.scpi_port, "visa": u.visa,
            "transport": u.transport, "channel": u.channel, "opMode": u.op_mode or None,
            "poll": f"{u.poll_ms} ms", "enabled": u.enabled, "online": u.online,
        })
    return out


def config_racks(db: Session):
    return [{"id": r.id, "name": r.name, "loc": r.loc, "cap": r.cap, "unitsAssigned": len(r.units)}
            for r in db.query(orm.Rack).all()]


def rack_slots(db: Session, rack_id: str):
    rack = db.get(orm.Rack, rack_id)
    if not rack:
        return []
    occ = {u.slot: u.name for u in rack.units}
    return [{"key": f"{rack_id}{i}", "label": f"Slot {i}", "occ": occ.get(i, ""), "empty": i not in occ}
            for i in range(1, rack.cap + 1)]


def unassigned_units(db: Session, rack_id: str):
    # In this build every unit belongs to a rack slot the moment it's created,
    # so "unassigned" is units from OTHER racks that could be dragged in.
    return [u.name for u in db.query(orm.Unit).filter(orm.Unit.rack_id != rack_id).all()]


def assign_unit(db: Session, slot_key: str, unit_name: str):
    rack_id, slot_num = slot_key[0], int(slot_key[1:])
    unit = db.get(orm.Unit, unit_name)
    if not unit:
        raise ValueError(f"Unknown unit {unit_name}")
    target_rack = db.get(orm.Rack, rack_id)
    if not target_rack:
        raise ValueError(f"Unknown rack {rack_id}")
    occupant = next((u for u in target_rack.units if u.slot == slot_num and u.name != unit_name), None)
    if occupant:
        occupant.slot = unit.slot if unit.rack_id == rack_id else occupant.slot
        occupant.rack_id = unit.rack_id
    unit.rack_id, unit.slot = rack_id, slot_num
    db.commit()
    return {"slots": rack_slots(db, rack_id), "palette": unassigned_units(db, rack_id)}
