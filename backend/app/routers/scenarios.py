from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, state
from ..db import get_db

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("/{scenario_id}")
def get_scenario(scenario_id: str):
    graph = state.scenario_graph()
    if graph["scenario"]["id"] != scenario_id:
        raise HTTPException(404, "Unknown scenario")
    return graph


@router.get("/{scenario_id}/nodes/{node_id}")
def get_node_props(scenario_id: str, node_id: str):
    props = state.node_props(node_id)
    if not props:
        raise HTTPException(404, "Unknown node")
    return props


@router.post("/{scenario_id}/run")
async def run_scenario(scenario_id: str, db: Session = Depends(get_db)):
    graph = state.scenario_graph()
    if graph["scenario"]["id"] != scenario_id:
        raise HTTPException(404, "Unknown scenario")
    run_id = state.create_run(db, graph["scenario"]["name"], graph["scenario"]["version"], [data.FEATURED_UNIT])
    await state.start_run(run_id)
    return state.run_detail(db, run_id)
