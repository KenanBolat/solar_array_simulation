"""Scenario graphs: persistence, editing, and the runner that walks them.

A scenario is a directed graph of typed blocks (see data.NODE_TYPES). The
runner starts at the `start` block and follows edges, dispatching real SCPI
for the blocks that touch the instrument and recording, per block, whether it
is waiting, running, finished or failed — which is what the canvas colours
itself from.

Every command a run sends goes into the same append-only audit log as a
manual one, and is also attached to the run so the builder can show the
command history for that run alone.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from . import data, orm, state
from .db import session_scope
from .scpi import CommandResult, Instrument

logger = logging.getLogger(__name__)

RUNNER_USER = "scenario"
STEP_PACING_S = 0.45      # a beat between steps so an operator can follow the run
_run_tasks: dict[str, asyncio.Task] = {}

# per-block lifecycle → the canvas colour code
READY, RUNNING, DONE, ERROR, SKIPPED = "ready", "running", "done", "error", "skipped"


def now_hhmmss() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _ms() -> int:
    return int(time.time() * 1000)


# ---------- graph ----------
def node_defaults(node_type: str) -> dict:
    spec = data.NODE_TYPES.get(node_type)
    return {p["key"]: p.get("default") for p in spec["params"]} if spec else {}


def resolve_curve(db: Session, params: dict) -> tuple[dict | None, str]:
    """The four SAS values an Apply Solar Profile block will actually send, and a
    caption naming where they came from. Returns (None, reason) when the block
    points at a preset that can no longer be used."""
    if params.get("source") != data.CURVE_PRESET:
        return ({k: float(params.get(k, 0) or 0) for k in ("isc", "imp", "vmp", "voc")}, "typed values")
    pid = int(params.get("preset") or 0)
    if not pid:
        return None, "no preset chosen"
    pr = db.get(orm.Preset, pid)
    if not pr:
        return None, "preset was deleted"
    if pr.mode != "SAS":
        return None, f"{pr.name} is a FIX preset"
    if not pr.enabled:
        return None, f"preset {pr.name} is disabled"
    return {"isc": pr.isc, "imp": pr.imp, "vmp": pr.vmp, "voc": pr.voc}, f"preset {pr.name}"


def resolve_target(db: Session, params: dict) -> tuple[str | None, str]:
    """The channel a Select Equipment block switches to, and why it cannot."""
    name = str(params.get("unit") or "").strip()
    if not name:
        return None, "no channel chosen"
    u = state.get_unit(db, name)
    if not u:
        return None, f"{name} is no longer configured"
    if not u.enabled:
        return None, f"{state.unit_label(u)} is disabled"
    return u.name, state.unit_label(u)


def _node_dict(n: orm.ScenarioNode, db: Session | None = None) -> dict:
    spec = data.NODE_TYPES.get(n.type, {})
    params = {**node_defaults(n.type), **json.loads(n.params or "{}")}
    sub = summarise(n.type, params)
    if n.type == "sas" and db is not None:
        curve, why = resolve_curve(db, params)
        sub = (f"{why} · Vmp {curve['vmp']:g} V · Imp {curve['imp']:g} A" if curve
               else f"⚠ {why}")
    if n.type == "target" and db is not None:
        name, why = resolve_target(db, params)
        sub = why if name else f"⚠ {why}"
    return {
        "id": n.id, "type": n.type, "kind": spec.get("kind", "action"),
        "badge": spec.get("badge", n.type.upper()),
        "label": n.label or spec.get("label", n.type),
        "x": n.x, "y": n.y, "params": params,
        "sub": sub,
        "help": spec.get("help", ""),
    }


def summarise(node_type: str, params: dict) -> str:
    """The one-line caption under a block's title on the canvas."""
    if node_type == "setv":
        return f"{float(params.get('volts', 0)):g} V"
    if node_type == "seti":
        return f"{float(params.get('amps', 0)):g} A"
    if node_type == "mode":
        return f"CURR:MODE {params.get('mode', 'FIX')}"
    if node_type == "output":
        return f"OUTP {params.get('on', 'ON')}"
    if node_type == "wait":
        return f"{int(params.get('ms', 0)):,} ms".replace(",", " ")
    if node_type == "sas":
        return f"Vmp {float(params.get('vmp', 0)):g} V · Imp {float(params.get('imp', 0)):g} A"
    if node_type == "threshold":
        unit = {"power": "W", "voltage": "V", "current": "A"}.get(params.get("source", "power"), "")
        return f"{params.get('source', 'power')} {params.get('op', '>')} {float(params.get('value', 0)):g} {unit}"
    if node_type == "measure":
        return "MEAS:VOLT? · FETC:CURR?"
    if node_type == "record":
        return "run log"
    if node_type == "shutdown":
        return "OUTP OFF"
    return ""


def walk(nodes: dict, out: dict, start: str, target0: str) -> dict[str, dict[str, set]]:
    """Follows every path from Start, carrying the channel a block runs against and
    the operating mode that channel is in. Both travel together: a Set Mode applies
    to whichever channel is current, so comparing modes across channels would be
    meaningless. A block reachable by several paths collects each state it may see.
    "?" as a mode means the channel was left in whatever it already was."""
    reached: dict[str, dict[str, set]] = {}
    stack: list[tuple[str, str, str]] = [(start, target0, "?")]
    seen_states: set[tuple[str, str, str]] = set()
    while stack:
        cur, tgt, mode = stack.pop()
        if (cur, tgt, mode) in seen_states:
            continue
        seen_states.add((cur, tgt, mode))
        slot = reached.setdefault(cur, {"targets": set(), "modes": set()})
        slot["targets"].add(tgt)
        slot["modes"].add(mode)
        node = nodes[cur]
        if node["type"] == "target":
            tgt = str(node["params"].get("unit") or "") or tgt
            mode = "?"                      # a different channel, in its own state
        elif node["type"] == "mode":
            mode = node["params"].get("mode", mode)
        stack.extend((e["to"], tgt, mode) for e in out.get(cur, []))
    return reached


def _edges_out(g: dict) -> dict[str, list]:
    out: dict[str, list] = {n["id"]: [] for n in g["nodes"]}
    for e in g["edges"]:
        out[e["from"]].append(e)
    return out


def graph(db: Session, scenario_id: str) -> dict | None:
    s = db.get(orm.Scenario, scenario_id)
    if not s:
        return None
    default_target = s.target_unit or data.FEATURED_UNIT
    g = {
        # targetUnit is the *effective* default — the same fallback start_run uses —
        # so the canvas can never name a different channel than the one dispatched to.
        "scenario": {"id": s.id, "name": s.name, "version": s.version, "state": s.state,
                      "targetUnit": default_target},
        "nodes": [_node_dict(n, db) for n in sorted(s.nodes, key=lambda n: n.id)],
        "edges": [{"id": e.id, "from": e.src, "to": e.dst, "fail": e.fail} for e in s.edges],
        "nodeTypes": [{"type": k, **v} for k, v in data.NODE_TYPES.items()],
    }
    # Tell each block which channel it will run against, so a scenario that
    # switches equipment part-way is readable on the canvas.
    nodes = {n["id"]: n for n in g["nodes"]}
    start = next((n["id"] for n in g["nodes"] if n["type"] == "start"), None)
    reached = walk(nodes, _edges_out(g), start, default_target) if start else {}
    for n in g["nodes"]:
        n["runsOn"] = sorted(reached.get(n["id"], {}).get("targets", set()))
    return g


def list_scenarios(db: Session) -> list[dict]:
    return [{"id": s.id, "name": s.name, "version": s.version, "state": s.state}
            for s in db.query(orm.Scenario).order_by(orm.Scenario.name).all()]


def add_node(db: Session, scenario_id: str, node_type: str, x: int, y: int) -> dict:
    if node_type not in data.NODE_TYPES:
        raise ValueError(f"Unknown block type {node_type}")
    s = db.get(orm.Scenario, scenario_id)
    if not s:
        raise ValueError("Unknown scenario")
    if node_type == "start" and any(n.type == "start" for n in s.nodes):
        raise ValueError("A scenario has exactly one Start block")
    # Slide the drop point clear of any block already there: an overlapped block
    # hides the one under it, which can then no longer be clicked or dragged.
    w, h = data.BLOCK_W + 16, data.BLOCK_H + 16
    x, y = max(0, int(x)), max(0, int(y))
    for _ in range(200):
        clash = next((o for o in s.nodes if abs(o.x - x) < w and abs(o.y - y) < h), None)
        if not clash:
            break
        x, y = clash.x + w, y
        if x > 1400 - data.BLOCK_W:            # ran off the right edge — next row down
            x, y = 40, y + h
    n = orm.ScenarioNode(id=f"n_{uuid.uuid4().hex[:8]}", scenario_id=scenario_id, type=node_type,
                          label="", x=x, y=y, params=json.dumps(node_defaults(node_type)))
    db.add(n)
    db.commit()
    return _node_dict(n, db)


def update_node(db: Session, node_id: str, x=None, y=None, params=None, label=None) -> dict | None:
    n = db.get(orm.ScenarioNode, node_id)
    if not n:
        return None
    if x is not None:
        n.x = int(x)
    if y is not None:
        n.y = int(y)
    if label is not None:
        n.label = label.strip()
    if params is not None:
        spec = data.NODE_TYPES.get(n.type, {"params": []})
        current = {**node_defaults(n.type), **json.loads(n.params or "{}")}
        # Reject keys this block does not have: silently dropping them would make
        # the editor look as though it saved a value that then reverts on reload.
        unknown = set(params) - {p["key"] for p in spec["params"]}
        if unknown:
            raise ValueError(f"{spec.get('label', n.type)} has no setting named {', '.join(sorted(unknown))}")
        for p in spec["params"]:
            if p["key"] not in params:
                continue
            raw = params[p["key"]]
            if p["type"] == "unit":
                name = str(raw or "").strip()
                if name:
                    u = state.get_unit(db, name)
                    if not u:
                        raise ValueError(f"No channel named {name} is configured")
                    if not u.enabled:
                        raise ValueError(f"{state.unit_label(u)} is disabled — enable it first")
                    name = u.name
                current[p["key"]] = name
            elif p["type"] == "preset":
                pid = int(raw or 0)
                if pid:
                    pr = db.get(orm.Preset, pid)
                    if not pr:
                        raise ValueError("That preset no longer exists")
                    if pr.mode != "SAS":
                        raise ValueError(f"{pr.name} is a FIX preset — this block needs a SAS one")
                current[p["key"]] = pid
            elif p["type"] == "number":
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    raise ValueError(f"{p['label']} must be a number")
                lo, hi = p.get("min"), p.get("max")
                if lo is not None and val < lo or hi is not None and val > hi:
                    raise ValueError(f"{p['label']} must be between {lo} and {hi}{(' ' + p['unit']) if p.get('unit') else ''}")
                current[p["key"]] = val
            else:
                if raw not in p.get("options", []):
                    raise ValueError(f"{p['label']} must be one of {', '.join(p.get('options', []))}")
                current[p["key"]] = raw
        # The coupling rules the instrument itself enforces. A preset was already
        # checked against them when it was stored, so only typed values are re-checked.
        if n.type == "sas" and current.get("source") != data.CURVE_PRESET:
            state.check_soft_limits("SAS", current)
        n.params = json.dumps(current)
    db.commit()
    return _node_dict(n, db)


def delete_node(db: Session, node_id: str) -> bool:
    n = db.get(orm.ScenarioNode, node_id)
    if not n:
        return False
    if n.type == "start":
        raise ValueError("The Start block cannot be deleted")
    db.query(orm.ScenarioEdge).filter(
        (orm.ScenarioEdge.src == node_id) | (orm.ScenarioEdge.dst == node_id)).delete(synchronize_session=False)
    db.delete(n)
    db.commit()
    return True


def add_edge(db: Session, scenario_id: str, src: str, dst: str, fail: bool) -> dict:
    if src == dst:
        raise ValueError("A block cannot connect to itself")
    s = db.get(orm.Scenario, scenario_id)
    if not s:
        raise ValueError("Unknown scenario")
    ids = {n.id: n for n in s.nodes}
    if src not in ids or dst not in ids:
        raise ValueError("Both ends must be blocks in this scenario")
    if ids[dst].type == "start":
        raise ValueError("Nothing connects into Start")
    if ids[src].type in ("end", "shutdown"):
        raise ValueError(f"{data.NODE_TYPES[ids[src].type]['label']} ends the run — it has no outgoing path")
    existing = [e for e in s.edges if e.src == src]
    if any(e.dst == dst for e in existing):
        raise ValueError("These blocks are already connected")
    # Only a check has two outcomes; everything else has a single next step.
    if ids[src].type == "threshold":
        if any(e.fail == fail for e in existing):
            raise ValueError(f"This check already has a {'fail' if fail else 'pass'} path")
    elif existing:
        raise ValueError("This block already has a next step — remove it first")
    e = orm.ScenarioEdge(scenario_id=scenario_id, src=src, dst=dst, fail=bool(fail))
    db.add(e)
    db.commit()
    return {"id": e.id, "from": e.src, "to": e.dst, "fail": e.fail}


def delete_edge(db: Session, edge_id: int) -> bool:
    e = db.get(orm.ScenarioEdge, edge_id)
    if not e:
        return False
    db.delete(e)
    db.commit()
    return True


def seed_default(db: Session):
    if db.query(orm.Scenario).first():
        return
    s = orm.Scenario(id=data.DEFAULT_SCENARIO_ID, name="Eclipse Cycle — Panel A", version="v1.4", state="DRAFT")
    db.add(s)
    for nid, ntype, x, y, params in data.DEFAULT_NODES:
        db.add(orm.ScenarioNode(id=nid, scenario_id=s.id, type=ntype, label="", x=x, y=y,
                                 params=json.dumps({**node_defaults(ntype), **params})))
    for src, dst, fail in data.DEFAULT_EDGES:
        db.add(orm.ScenarioEdge(scenario_id=s.id, src=src, dst=dst, fail=fail))
    db.commit()


# ---------- validation ----------
def validate(db: Session, scenario_id: str) -> dict:
    g = graph(db, scenario_id)
    if not g:
        return {"ok": False, "problems": ["Unknown scenario"]}
    nodes = {n["id"]: n for n in g["nodes"]}
    out = _edges_out(g)
    problems = []
    starts = [n for n in nodes.values() if n["type"] == "start"]
    if len(starts) != 1:
        problems.append(f"{len(starts)} Start blocks — a scenario needs exactly one")
    for n in nodes.values():
        if n["type"] in ("end", "shutdown"):
            continue
        if not out[n["id"]]:
            problems.append(f"{n['label']} has no next step")
        if n["type"] == "threshold" and not any(e["fail"] for e in out[n["id"]]):
            problems.append(f"{n['label']} has no fail path")
    # a solar profile block must have a curve it can actually send
    for n in nodes.values():
        if n["type"] == "sas":
            curve, why = resolve_curve(db, n["params"])
            if not curve:
                problems.append(f"{n['label']} has no usable curve — {why}")
        # a Select Equipment block must name a channel that still exists
        if n["type"] == "target":
            name, why = resolve_target(db, n["params"])
            if not name:
                problems.append(f"{n['label']} has no usable channel — {why}")

    warnings = []
    if starts:
        reached = walk(nodes, out, starts[0]["id"], g["scenario"]["targetUnit"])
        uncovered = _uncovered_curve(nodes, out, starts[0]["id"], g["scenario"]["targetUnit"])
        for n in nodes.values():
            if n["id"] not in reached:
                problems.append(f"{n['label']} is never reached from Start")
                continue
            here = reached[n["id"]]["modes"]
            # VOLT / CURR are refused with 315 while the channel is in SAS mode.
            if n["type"] in ("setv", "seti") and "SAS" in here:
                problems.append(
                    f"{n['label']} runs while the channel is in SAS mode — the instrument answers "
                    f"315 settings conflict. Switch back to FIX first, or use Apply Solar Profile.")
            # Entering SAS without programming a curve leaves whatever was there before.
            if n["type"] == "output" and str(n["params"].get("on", "")).upper() == "ON" and "SAS" in here:
                if n["id"] in uncovered:
                    warnings.append(
                        f"{n['label']} energises the output in SAS mode with no Apply Solar Profile "
                        f"before it — the channel keeps whatever curve was last programmed.")
            # A curve programmed on a channel that never leaves FIX is stored and ignored.
            if n["type"] == "sas" and here and "SAS" not in here:
                warnings.append(
                    f"{n['label']} only ever runs while the channel is in FIX mode — the curve is "
                    f"accepted but ignored until a Set Mode block switches the channel to SAS.")
    return {"ok": not problems, "problems": problems, "warnings": warnings}


def _uncovered_curve(nodes: dict, out: dict, start: str, target0: str) -> set[str]:
    """Blocks reachable by at least one path that never programmed a curve on the
    channel current at that point. Switching equipment resets the cover, because a
    curve sent to one channel says nothing about another."""
    bad: set[str] = set()
    seen: set[tuple[str, str, bool]] = set()
    stack: list[tuple[str, str, bool]] = [(start, target0, False)]
    while stack:
        cur, tgt, covered = stack.pop()
        if (cur, tgt, covered) in seen:
            continue
        seen.add((cur, tgt, covered))
        if not covered:
            bad.add(cur)
        node = nodes[cur]
        if node["type"] == "target":
            nxt = str(node["params"].get("unit") or "") or tgt
            if nxt != tgt:
                tgt, covered = nxt, False
        elif node["type"] == "sas":
            covered = True
        stack.extend((e["to"], tgt, covered) for e in out.get(cur, []))
    return bad


def estimate_ms(db: Session, scenario_id: str) -> int:
    g = graph(db, scenario_id)
    if not g:
        return 0
    total = 0
    for n in g["nodes"]:
        total += int(STEP_PACING_S * 1000)
        if n["type"] == "wait":
            total += int(n["params"].get("ms", 0))
    return total


# ---------- runner ----------
def _set_node_state(run: orm.ScenarioRun, node_id: str, value: str):
    states = json.loads(run.node_states or "{}")
    states[node_id] = value
    run.node_states = json.dumps(states)


def _event(db: Session, run_id: str, node: str, lvl: str, m: str,
           result: CommandResult | None = None, reading: dict | None = None, unit: str = ""):
    db.add(orm.ScenarioRunEvent(
        run_id=run_id, t=now_hhmmss(), node=node, lvl=lvl, m=m, unit=unit,
        scpi=result.sent if result else "", response=(result.response or "") if result else "",
        latency_ms=result.latency_ms if result else 0, ts_ms=_ms(),
        voltage=reading.get("voltage") if reading else None,
        current=reading.get("current") if reading else None,
        power=reading.get("power") if reading else None))


def create_run(db: Session, scenario_id: str, by: str = "", dry: bool = False) -> str:
    by = by or data.DEFAULT_USER
    s = db.get(orm.Scenario, scenario_id)
    if not s:
        raise ValueError("Unknown scenario")
    target = s.target_unit or data.FEATURED_UNIT
    count = db.query(orm.ScenarioRun).count()
    run_id = f"RUN-{8843 + count}"
    states = {n.id: READY for n in s.nodes}
    db.add(orm.ScenarioRun(
        id=run_id, scenario=s.name, scenario_id=s.id, version=s.version, status="Queued",
        dry=dry, progress=0, targets=target, by=by, started=now_hhmmss(), finished="—", dur="0s",
        node_states=json.dumps(states), est_ms=estimate_ms(db, scenario_id)))
    db.commit()
    return run_id


class StepRefused(Exception):
    """A block cannot run as configured — nothing was sent to the instrument.
    Treated exactly like a failed step so the fail path still applies."""


def _dispatch_threaded(run_id: str, node: dict, inst: Instrument, last: dict) -> tuple[CommandResult | None, str, str]:
    """Runs a block off the event loop, in its own session. Returns
    (result, message, refusal) — refusal is set when the block could not run."""
    try:
        with session_scope() as db:
            result, msg = _dispatch(db, run_id, node, inst, last)
        return result, msg, ""
    except StepRefused as e:
        return None, "", str(e)


def _dispatch(db: Session, run_id: str, node: dict, inst: Instrument, last: dict) -> tuple[CommandResult | None, str]:
    """Run one block against the instrument. Returns (result, human message).
    Blocks that don't touch the instrument return (None, message)."""
    t, p = node["type"], node["params"]
    if t == "mode":
        return inst.set_mode(p["mode"]), f"mode → {p['mode']}"
    if t == "setv":
        return inst.set_voltage(float(p["volts"])), f"voltage → {float(p['volts']):g} V"
    if t == "seti":
        return inst.set_current(float(p["amps"])), f"current limit → {float(p['amps']):g} A"
    if t == "sas":
        curve, why = resolve_curve(db, p)
        if not curve:
            raise StepRefused(f"solar profile has no usable curve — {why}")
        return (inst.apply_sas_curve(curve["isc"], curve["imp"], curve["vmp"], curve["voc"]),
                f"curve from {why} → Vmp {curve['vmp']:g} V / Imp {curve['imp']:g} A "
                f"/ Voc {curve['voc']:g} V / Isc {curve['isc']:g} A")
    if t == "output":
        on = str(p["on"]).upper() == "ON"
        return inst.set_output(on), f"output → {'ON' if on else 'OFF'}"
    if t == "shutdown":
        return inst.safe_shutdown(), "safe shutdown — output OFF"
    if t == "measure":
        result, reading = inst.measure()
        if result.ok and reading:
            last.update({"voltage": reading.voltage, "current": reading.current, "power": reading.power})
            return result, f"{reading.voltage:.3f} V · {reading.current:.3f} A · {reading.power:.2f} W"
        return result, "measurement failed"
    if t == "record":
        if not last:
            return None, "nothing measured yet — recorded as empty"
        return None, (f"recorded {last['voltage']:.3f} V · {last['current']:.3f} A · {last['power']:.2f} W")
    if t == "export":
        measured_only = p.get("what") == data.EXPORT_MEASURED
        path, rows = write_run_csv(db, run_id, measured_only=measured_only)
        if not rows:
            return None, ("no measurements to export yet — add a Read V · I · P block before this one"
                          if measured_only else "nothing to export yet")
        return None, f"exported {rows} row(s) to {path.name}"
    if t in ("start", "end", "wait", "threshold"):
        return None, ""
    return None, f"block type {t} has no action"


def _check(node: dict, last: dict) -> tuple[bool, str]:
    p = node["params"]
    src = p.get("source", "power")
    value = last.get(src)
    if value is None:
        return False, f"no {src} reading available — treating the check as failed"
    threshold = float(p.get("value", 0))
    op = p.get("op", ">")
    ok = {">": value > threshold, ">=": value >= threshold,
          "<": value < threshold, "<=": value <= threshold}[op]
    unit = {"power": "W", "voltage": "V", "current": "A"}[src]
    return ok, f"{src} {value:.3f} {unit} {op} {threshold:g} {unit} → {'pass' if ok else 'fail'}"


async def start_run(run_id: str):
    with session_scope() as db:
        run = db.get(orm.ScenarioRun, run_id)
        if not run or run.status == "Running":
            return
        g = graph(db, run.scenario_id)
        if not g:
            run.status = "Failed"
            return
        unit = state.get_unit(db, run.targets.split(",")[0])
        if not unit:
            run.status = "Failed"
            return
        inst = Instrument.for_unit(unit)
        unit_name = unit.name
        unit_show = state.unit_label(unit)
        run.status, run.progress = "Running", 0
        run.started, run.started_ms, run.finished = now_hhmmss(), _ms(), "—"
        run.node_states = json.dumps({n["id"]: READY for n in g["nodes"]})
        _event(db, run_id, "start", "info",
                f"Run accepted · {g['scenario']['name']} {g['scenario']['version']} · target {unit_show}",
                unit=unit_name)

    nodes = {n["id"]: n for n in g["nodes"]}
    out = _edges_out(g)
    start_node = next((n["id"] for n in g["nodes"] if n["type"] == "start"), None)

    # The channel the run is dispatching to. A Select Equipment block moves it, so
    # it is rebound mid-run rather than fixed when the run was accepted.
    class Target:
        def __init__(self, inst: Instrument, name: str, show: str):
            self.inst, self.name, self.show = inst, name, show
            self.touched = [name]

        def switch(self, db: Session, name: str) -> str:
            u = state.get_unit(db, name)
            if not u:
                raise StepRefused(f"{name} is no longer configured")
            if not u.enabled:
                raise StepRefused(f"{state.unit_label(u)} is disabled")
            self.inst, self.name, self.show = Instrument.for_unit(u), u.name, state.unit_label(u)
            if u.name not in self.touched:
                self.touched.append(u.name)
            return self.show

    target = Target(inst, unit_name, unit_show)

    async def drive():
        last: dict = {}
        cur = start_node
        visited = 0
        total = max(1, len(nodes))
        try:
            while cur:
                await asyncio.sleep(STEP_PACING_S)
                node = nodes[cur]

                with session_scope() as db:
                    run = db.get(orm.ScenarioRun, run_id)
                    if not run or run.status != "Running":
                        return
                    run.current_node = cur
                    _set_node_state(run, cur, RUNNING)

                # the blocking parts happen outside the DB session
                refused = ""
                if node["type"] == "wait":
                    await asyncio.sleep(int(node["params"].get("ms", 0)) / 1000)
                    result, msg = None, f"waited {int(node['params'].get('ms', 0))} ms"
                elif node["type"] == "threshold":
                    result, msg = None, ""
                elif node["type"] == "target":
                    # Nothing is sent; the following steps simply go elsewhere. The
                    # last reading belongs to the old channel, so it is dropped.
                    result, msg = None, ""
                    try:
                        with session_scope() as db:
                            msg = f"following steps run on {target.switch(db, str(node['params'].get('unit') or ''))}"
                        last.clear()
                    except StepRefused as e:
                        refused = str(e)
                else:
                    result, msg, refused = await asyncio.to_thread(_dispatch_threaded, run_id, node, target.inst, last)

                failed = refused != "" or (result is not None and not result.ok)
                branch_fail = False
                if node["type"] == "threshold":
                    passed, msg = _check(node, last)
                    branch_fail = not passed

                with session_scope() as db:
                    run = db.get(orm.ScenarioRun, run_id)
                    if not run or run.status != "Running":
                        return
                    if result is not None:
                        state.log_command(db, RUNNER_USER, target.name, f"scenario:{node['label']}", result)
                    # keep the run's target list honest as it moves between channels
                    if run.targets != ",".join(target.touched):
                        run.targets = ",".join(target.touched)
                    if failed:
                        _set_node_state(run, cur, ERROR)
                        detail = refused or result.describe()
                        _event(db, run_id, cur, "err", f"{node['label']} · {detail}", result, unit=target.name)
                    else:
                        _set_node_state(run, cur, DONE)
                        lvl = "warn" if branch_fail else "ok"
                        # Only the steps that actually produced a reading carry one, so
                        # an exported row never implies a measurement the step never took.
                        reading = last if node["type"] in ("measure", "record") and last else None
                        _event(db, run_id, cur, lvl, f"{node['label']}{' · ' + msg if msg else ''}",
                               result, reading, unit=target.name)
                    visited += 1
                    run.progress = min(99, round(visited / total * 100))

                # choose the next block
                edges = out.get(cur, [])
                if failed:
                    nxt = next((e["to"] for e in edges if e["fail"]), None)
                    if nxt is None:
                        with session_scope() as db:
                            run = db.get(orm.ScenarioRun, run_id)
                            if run and run.status == "Running":
                                run.status, run.finished, run.ended_ms = "Failed", now_hhmmss(), _ms()
                                run.current_node = ""
                                run.dur = _fmt_dur(run)
                                _event(db, run_id, cur, "err", "Run stopped — the step failed and there is no fail path",
                                       unit=target.name)
                        return
                elif node["type"] == "threshold":
                    nxt = next((e["to"] for e in edges if e["fail"] is branch_fail), None)
                else:
                    nxt = next((e["to"] for e in edges if not e["fail"]), None)

                if nxt is None or node["type"] in ("end", "shutdown"):
                    with session_scope() as db:
                        run = db.get(orm.ScenarioRun, run_id)
                        if run and run.status == "Running":
                            # Reaching a Safe Shutdown block means a check did not
                            # pass, so the run failed — "Aborted" is kept for the
                            # case where an operator stopped it by hand.
                            ended = node["type"] == "shutdown"
                            run.status = "Failed" if ended else "Completed"
                            run.progress = 100
                            run.finished, run.ended_ms, run.current_node = now_hhmmss(), _ms(), ""
                            run.dur = _fmt_dur(run)
                            states = json.loads(run.node_states)
                            for nid, st in states.items():
                                if st == READY:
                                    states[nid] = SKIPPED
                            run.node_states = json.dumps(states)
                            _event(db, run_id, cur, "err" if ended else "ok",
                                   "Run ended on Safe Shutdown — the output is de-energised"
                                   if ended else "Run completed", unit=target.name)
                    return
                cur = nxt
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scenario run %s failed", run_id)
            with session_scope() as db:
                run = db.get(orm.ScenarioRun, run_id)
                if run and run.status == "Running":
                    run.status, run.finished, run.ended_ms = "Failed", now_hhmmss(), _ms()
                    run.dur = _fmt_dur(run)
                    _event(db, run_id, cur or "", "err", "Run aborted by an internal error", unit=target.name)

    _run_tasks[run_id] = asyncio.create_task(drive())


# ---------- CSV export ----------
EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"

CSV_HEADER = ["run", "scenario", "version", "channel", "time_utc", "elapsed_s", "block",
              "level", "message", "scpi_sent", "response", "latency_ms",
              "voltage_v", "current_a", "power_w"]


def run_csv_rows(db: Session, run_id: str, measured_only: bool = False) -> list[list]:
    """One row per step, in the order the run took them. Numbers stay numbers so
    the file charts in Excel without cleaning."""
    run = db.get(orm.ScenarioRun, run_id)
    if not run:
        return []
    labels = {}
    s = db.get(orm.Scenario, run.scenario_id)
    if s:
        labels = {n.id: _node_dict(n, db)["label"] for n in s.nodes}
    events = (db.query(orm.ScenarioRunEvent)
              .filter(orm.ScenarioRunEvent.run_id == run_id)
              .order_by(orm.ScenarioRunEvent.id.asc()).all())
    rows = []
    for e in events:
        if measured_only and e.voltage is None:
            continue
        elapsed = round((e.ts_ms - run.started_ms) / 1000, 3) if e.ts_ms and run.started_ms else ""
        rows.append([run.id, run.scenario, run.version, e.unit, e.t, elapsed,
                      labels.get(e.node, e.node), e.lvl, e.m, e.scpi, e.response,
                      e.latency_ms or "", e.voltage if e.voltage is not None else "",
                      e.current if e.current is not None else "",
                      e.power if e.power is not None else ""])
    return rows


def run_csv_text(db: Session, run_id: str, measured_only: bool = False) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_HEADER)
    w.writerows(run_csv_rows(db, run_id, measured_only))
    return buf.getvalue()


def write_run_csv(db: Session, run_id: str, measured_only: bool = False) -> tuple[Path, int]:
    """Writes the run-so-far to backend/exports/ and returns (path, row count)."""
    rows = run_csv_rows(db, run_id, measured_only)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "-measurements" if measured_only else ""
    path = EXPORT_DIR / f"{run_id}{suffix}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(CSV_HEADER)
        w.writerows(rows)
    return path, len(rows)


def _fmt_dur(run: orm.ScenarioRun) -> str:
    if not run.started_ms or not run.ended_ms:
        return "0s"
    secs = max(0, (run.ended_ms - run.started_ms) / 1000)
    return f"{int(secs // 60)}m {secs % 60:.0f}s" if secs >= 60 else f"{secs:.1f}s"


def abort_run(db: Session, run_id: str) -> dict:
    run = db.get(orm.ScenarioRun, run_id)
    if not run or run.status != "Running":
        return {"ok": False, "message": "Run is not active"}
    task = _run_tasks.pop(run_id, None)
    if task:
        task.cancel()
    run.status, run.finished, run.ended_ms = "Aborted", now_hhmmss(), _ms()
    run.dur, run.current_node = _fmt_dur(run), ""
    states = json.loads(run.node_states or "{}")
    for nid, st in states.items():
        if st in (READY, RUNNING):
            states[nid] = SKIPPED
    run.node_states = json.dumps(states)
    _event(db, run_id, "", "err", "Abort requested by the operator")
    db.commit()
    return {"ok": True, "message": f"Abort dispatched · {run_id}"}


def run_view(db: Session, run_id: str) -> dict | None:
    """Everything the live canvas needs in one poll."""
    run = db.get(orm.ScenarioRun, run_id)
    if not run:
        return None
    events = (db.query(orm.ScenarioRunEvent).filter(orm.ScenarioRunEvent.run_id == run_id)
              .order_by(orm.ScenarioRunEvent.id.asc()).all())
    states = json.loads(run.node_states or "{}")
    # Elapsed is measured here, against the clock that stamped started_ms. A browser
    # subtracting started_ms from its own Date.now() reads nonsense whenever the two
    # machines' clocks differ, which on a lab LAN they routinely do.
    elapsed_ms = 0
    if run.started_ms:
        elapsed_ms = max(0, (run.ended_ms or _ms()) - run.started_ms)
    return {
        "id": run.id, "scenario": run.scenario, "scenarioId": run.scenario_id, "version": run.version,
        "status": run.status, "progress": run.progress, "targets": run.targets.split(",") if run.targets else [],
        "by": run.by, "started": run.started, "finished": run.finished, "dur": run.dur,
        "currentNode": run.current_node or None,
        "nodeStates": states,
        "startedMs": run.started_ms, "endedMs": run.ended_ms, "estMs": run.est_ms,
        "elapsedMs": elapsed_ms,
        "stepsDone": sum(1 for v in states.values() if v in (DONE, ERROR)),
        "stepsTotal": len(states),
        "events": [{"t": e.t, "node": e.node, "lvl": e.lvl, "m": e.m, "scpi": e.scpi,
                     "resp": e.response, "lat": e.latency_ms, "unit": e.unit or "",
                     # offset from the run's start, so the strip can mark where each step ran
                     "atMs": max(0, e.ts_ms - run.started_ms) if e.ts_ms and run.started_ms else None}
                    for e in events],
    }


def active_run(db: Session, scenario_id: str) -> dict | None:
    run = (db.query(orm.ScenarioRun)
           .filter(orm.ScenarioRun.scenario_id == scenario_id, orm.ScenarioRun.status == "Running")
           .first())
    return run_view(db, run.id) if run else None


def latest_run(db: Session, scenario_id: str) -> dict | None:
    run = (db.query(orm.ScenarioRun)
           .filter(orm.ScenarioRun.scenario_id == scenario_id)
           .order_by(orm.ScenarioRun.id.desc()).first())
    return run_view(db, run.id) if run else None
