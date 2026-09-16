"""Minimal but real scenario interpreter.

Walks the graph from Start, executing nodes against target devices through
the command service (so every action is queued, audited and metered).
Supports: set_output_state, configure_parameters, apply_profile, wait,
read/record_measurement, threshold_check, repeat (bounded), safe_shutdown,
notification, condition/branch (boolean on last threshold), comment.

Safety: refuses offline devices, enforces bounded iteration, respects
pause/abort flags, and runs each target serially (never concurrent writes
to the same instrument -- the per-device queue also guarantees this).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.logging import get_logger
from app.metrics import scenario_runs_total
from app.models import Device, ScenarioRun, ScenarioRunEvent
from app.services.command_service import run_command
from app.services.eventbus import get_event_bus
from app.services.scenario_validation import MAX_REPEAT_ITERATIONS

log = get_logger("scenario")

# control flags keyed by run id
_run_control: dict[str, dict] = {}


def request_pause(run_id: str): _run_control.setdefault(run_id, {})["pause"] = True
def request_resume(run_id: str): _run_control.setdefault(run_id, {})["pause"] = False
def request_abort(run_id: str): _run_control.setdefault(run_id, {})["abort"] = True


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _emit(session, run_id, node_key, level, message, detail=None):
    session.add(ScenarioRunEvent(run_id=run_id, ts_utc=_utcnow(), node_key=node_key,
                                 level=level, message=message, detail=detail or {}))
    await session.flush()
    await get_event_bus().publish("scenario_progress", {
        "run_id": str(run_id), "node_key": node_key, "level": level,
        "message": message, "ts": _utcnow().isoformat()})


async def execute_run(run_id: uuid.UUID, nodes: list[dict], edges: list[dict],
                      actor: str) -> None:
    rid = str(run_id)
    _run_control[rid] = {"pause": False, "abort": False}
    by_key = {n["node_key"]: n for n in nodes}
    nexts: dict[str, list[str]] = {n["node_key"]: [] for n in nodes}
    for e in edges:
        nexts.setdefault(e["source"], []).append(e["target"])

    async with SessionLocal() as session:
        run = (await session.execute(select(ScenarioRun).where(ScenarioRun.id == run_id))).scalar_one()
        devices = (await session.execute(
            select(Device).where(Device.id.in_(run.target_device_ids)))).scalars().all()

        # SAFETY: offline devices are not eligible
        offline = [str(d.id) for d in devices
                   if (d.last_state or {}).get("device_state") == "offline"]
        if offline and not run.dry_run:
            run.status = "failed"
            run.finished_utc = _utcnow()
            await _emit(session, run_id, None, "error",
                        f"refusing to run: offline devices {offline}")
            await session.commit()
            scenario_runs_total.labels("failed").inc()
            return

        run.status = "running"
        run.started_utc = _utcnow()
        await _emit(session, run_id, None, "info",
                    f"run started ({'DRY-RUN' if run.dry_run else 'LIVE'}) on {len(devices)} device(s)")
        await session.commit()

        start = next((n for n in nodes if n["type"] == "start"), None)
        total = max(len(nodes), 1)
        visited = 0
        last_condition = True

        async def step(node_key: str, depth: int = 0):
            nonlocal visited, last_condition
            if depth > MAX_REPEAT_ITERATIONS:
                raise RuntimeError("iteration bound exceeded")
            ctrl = _run_control.get(rid, {})
            if ctrl.get("abort"):
                raise asyncio.CancelledError()
            while ctrl.get("pause"):
                run.status = "paused"
                await session.commit()
                await asyncio.sleep(0.5)
                ctrl = _run_control.get(rid, {})
                if ctrl.get("abort"):
                    raise asyncio.CancelledError()
            if run.status == "paused":
                run.status = "running"

            node = by_key[node_key]
            ntype = node["type"]
            cfg = node.get("config") or {}
            visited += 1
            run.progress = min(1.0, visited / (total * 1.0))

            if ntype in ("start", "comment"):
                pass
            elif ntype == "end":
                await _emit(session, run_id, node_key, "info", "reached End")
                return
            elif ntype == "wait":
                secs = float(cfg.get("seconds", 1))
                await _emit(session, run_id, node_key, "info", f"wait {secs}s")
                if not run.dry_run:
                    await asyncio.sleep(min(secs, 30))
            elif ntype in ("set_output_state", "configure_parameters", "apply_profile",
                           "send_command", "safe_shutdown"):
                tid = {
                    "set_output_state": "output_on" if cfg.get("enabled", True) else "output_off",
                    "configure_parameters": "configure_sas_table",
                    "apply_profile": "apply_profile",
                    "safe_shutdown": "safe_shutdown",
                    "send_command": cfg.get("template_id", "read_measurements"),
                }[ntype]
                params = cfg.get("params", {})
                for d in devices:
                    if run.dry_run:
                        await _emit(session, run_id, node_key, "info",
                                    f"[dry-run] would run {tid} on {d.name}")
                        continue
                    res = await run_command(session, d, tid, params, actor=actor,
                                            confirmed=True, scenario_run_id=run_id)
                    await _emit(session, run_id, node_key,
                                "info" if res.status == "completed" else "warn",
                                f"{tid} on {d.name}: {res.status}")
            elif ntype in ("read_measurement", "record_measurement"):
                for d in devices:
                    st = d.last_state or {}
                    await _emit(session, run_id, node_key, "info",
                                f"measure {d.name}: V={st.get('voltage_v')} I={st.get('current_a')} P={st.get('power_w')}")
            elif ntype in ("threshold_check", "condition"):
                field = cfg.get("field", "power_w")
                op = cfg.get("op", ">=")
                thr = float(cfg.get("value", 0))
                results = []
                for d in devices:
                    val = float((d.last_state or {}).get(field, 0) or 0)
                    ok = (val >= thr) if op == ">=" else (val <= thr) if op == "<=" else (val == thr)
                    results.append(ok)
                last_condition = all(results)
                await _emit(session, run_id, node_key,
                            "info" if last_condition else "warn",
                            f"threshold {field} {op} {thr}: {'PASS' if last_condition else 'FAIL'}")
            elif ntype == "branch":
                outs = nexts.get(node_key, [])
                chosen = outs[0] if last_condition or len(outs) == 1 else outs[-1]
                if chosen:
                    await step(chosen, depth + 1)
                return
            elif ntype == "repeat":
                iters = int(cfg.get("max_iterations", 1))
                body = nexts.get(node_key, [])
                for _ in range(min(iters, MAX_REPEAT_ITERATIONS)):
                    for b in body:
                        await step(b, depth + 1)
                return
            elif ntype == "notification":
                await _emit(session, run_id, node_key, "info",
                            cfg.get("message", "notification"))

            await session.commit()
            for nxt in nexts.get(node_key, []):
                await step(nxt, depth + 1)

        try:
            if start is None:
                raise RuntimeError("no Start node")
            await step(start["node_key"])
            run.status = "completed"
            scenario_runs_total.labels("completed").inc()
            await _emit(session, run_id, None, "info", "run completed")
        except asyncio.CancelledError:
            run.status = "aborted"
            scenario_runs_total.labels("aborted").inc()
            await _emit(session, run_id, None, "warn", "run aborted by operator")
        except Exception as exc:
            run.status = "failed"
            scenario_runs_total.labels("failed").inc()
            await _emit(session, run_id, None, "error", f"run failed: {exc}")
        finally:
            run.finished_utc = _utcnow()
            run.progress = 1.0
            await session.commit()
            _run_control.pop(rid, None)
