from fastapi import APIRouter, HTTPException
from ..state import state

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(filter: str = "All"):
    return state.runs_view(filter)


@router.get("/{run_id}")
def get_run(run_id: str):
    r = state.run_detail(run_id)
    if not r:
        raise HTTPException(404, "Unknown run")
    return r


@router.post("/{run_id}/start")
async def start_run(run_id: str):
    if run_id not in state.runs:
        raise HTTPException(404, "Unknown run")
    await state.start_run(run_id)
    return state.run_detail(run_id)


@router.post("/{run_id}/pause")
def pause_run(run_id: str):
    return state.pause_run(run_id)


@router.post("/{run_id}/abort")
def abort_run(run_id: str):
    return state.abort_run(run_id)
