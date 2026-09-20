from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, orm, scenario, state
from ..db import get_db
from ..models import AddEdgeRequest, AddNodeRequest, UpdateNodeRequest

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
    g["run"] = scenario.active_run(db, scenario_id) or scenario.latest_run(db, scenario_id)
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
    _graph_or_404(db, scenario_id)
    return scenario.active_run(db, scenario_id) or scenario.latest_run(db, scenario_id) or {}


@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str, db: Session = Depends(get_db)):
    g = _graph_or_404(db, scenario_id)

    check = scenario.validate(db, scenario_id)
    if not check["ok"]:
        raise HTTPException(400, "Scenario is not runnable — " + "; ".join(check["problems"]))

    # Every channel the scenario may dispatch to must be up, not only the default —
    # a Select Equipment block can send later steps somewhere else entirely.
    wanted = {g["scenario"]["targetUnit"] or data.FEATURED_UNIT}
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

    run_id = scenario.create_run(db, scenario_id)
    await scenario.start_run(run_id)
    return scenario.run_view(db, run_id)


@router.post("/{scenario_id}/abort")
def abort(scenario_id: str, db: Session = Depends(get_db)):
    run = db.query(orm.ScenarioRun).filter(orm.ScenarioRun.scenario_id == scenario_id,
                                            orm.ScenarioRun.status == "Running").first()
    if not run:
        raise HTTPException(409, "No run is active for this scenario")
    return scenario.abort_run(db, run.id)
