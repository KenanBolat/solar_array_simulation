from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, orm, scenario, state
from ..db import get_db
from ..models import AddEdgeRequest, AddNodeRequest, TargetsRequest, UpdateNodeRequest

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _graph_or_404(db: Session, scenario_id: str):
    g = scenario.graph(db, scenario_id)
    if not g:
        raise HTTPException(404, "Unknown scenario")
    return g


@router.get("")
def list_scenarios(db: Session = Depends(get_db)):
    return scenario.list_scenarios(db)


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db)):
    g = _graph_or_404(db, scenario_id)
    g["validation"] = scenario.validate(db, scenario_id)
    g["estMs"] = scenario.estimate_ms(db, scenario_id)
    g["runs"] = scenario.current_batch(db, scenario_id)
    return g


@router.post("/{scenario_id}/nodes")
def add_node(scenario_id: str, body: AddNodeRequest, db: Session = Depends(get_db)):
    try:
        return scenario.add_node(db, scenario_id, body.type, body.x, body.y)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/{scenario_id}/nodes/{node_id}")
def update_node(scenario_id: str, node_id: str, body: UpdateNodeRequest, db: Session = Depends(get_db)):
    try:
        n = scenario.update_node(db, node_id, body.x, body.y, body.params, body.label)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not n:
        raise HTTPException(404, "Unknown block")
    return n


@router.delete("/{scenario_id}/nodes/{node_id}")
def delete_node(scenario_id: str, node_id: str, db: Session = Depends(get_db)):
    try:
        ok = scenario.delete_node(db, node_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not ok:
        raise HTTPException(404, "Unknown block")
    return {"ok": True}


@router.post("/{scenario_id}/edges")
def add_edge(scenario_id: str, body: AddEdgeRequest, db: Session = Depends(get_db)):
    try:
        return scenario.add_edge(db, scenario_id, body.src, body.dst, body.fail)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{scenario_id}/edges/{edge_id}")
def delete_edge(scenario_id: str, edge_id: int, db: Session = Depends(get_db)):
    if not scenario.delete_edge(db, edge_id):
        raise HTTPException(404, "Unknown connection")
    return {"ok": True}


@router.get("/{scenario_id}/validate")
def validate(scenario_id: str, db: Session = Depends(get_db)):
    _graph_or_404(db, scenario_id)
    return scenario.validate(db, scenario_id)


@router.get("/{scenario_id}/run")
def current_run(scenario_id: str, db: Session = Depends(get_db)):
    """Every run of the current batch — one per selected channel."""
    _graph_or_404(db, scenario_id)
    return {"runs": scenario.current_batch(db, scenario_id)}


@router.post("/{scenario_id}/targets")
def set_targets(scenario_id: str, body: TargetsRequest, db: Session = Depends(get_db)):
    """Which instruments and channels this scenario runs on, and whether they run
    together. A scenario is tied to nothing until this is set."""
    _graph_or_404(db, scenario_id)
    try:
        return scenario.set_targets(db, scenario_id, body.targets, body.parallel)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str, db: Session = Depends(get_db)):
    g = _graph_or_404(db, scenario_id)

    check = scenario.validate(db, scenario_id)
    if not check["ok"]:
        raise HTTPException(400, "Scenario is not runnable — " + "; ".join(check["problems"]))

    # Every channel the scenario may dispatch to must be up — the ones selected to
    # run on, and any a Select Equipment block redirects later steps to.
    wanted = set(g["scenario"]["targets"])
    wanted |= {t for n in g["nodes"] for t in n.get("runsOn", []) if t}
    for name in sorted(wanted):
        target = state.get_unit(db, name)
        if not target or not target.enabled or not target.online:
            raise HTTPException(
                409, f"{state.unit_label(target) if target else name} is not active "
                     f"(enabled + reachable) — cannot dispatch a run that uses it")

    if db.query(orm.ScenarioRun).filter(orm.ScenarioRun.scenario_id == scenario_id,
                                        orm.ScenarioRun.status == "Running").first():
        raise HTTPException(409, f"{g['scenario']['name']} is already running")

    started = await scenario.start_batch(db, scenario_id)
    return {**started, "runs": scenario.current_batch(db, scenario_id)}


@router.post("/{scenario_id}/reset")
def reset(scenario_id: str, db: Session = Depends(get_db)):
    """Get a scenario out of a state it will not start from: stop anything still
    running, clear the last run off the canvas, and re-check the channels."""
    _graph_or_404(db, scenario_id)
    return scenario.reset_scenario(db, scenario_id)


@router.post("/{scenario_id}/abort")
def abort(scenario_id: str, db: Session = Depends(get_db)):
    """Stops the whole batch, not just one channel — a scenario running on four
    channels must not leave three of them going when the operator hits Abort."""
    runs = db.query(orm.ScenarioRun).filter(orm.ScenarioRun.scenario_id == scenario_id,
                                             orm.ScenarioRun.status == "Running").all()
    if not runs:
        raise HTTPException(409, "No run is active for this scenario")
    scenario.cancel_batch(runs[0].batch or runs[0].id)
    msgs = [scenario.abort_run(db, r.id)["message"] for r in runs]
    return {"ok": True, "message": " · ".join(msgs)}
