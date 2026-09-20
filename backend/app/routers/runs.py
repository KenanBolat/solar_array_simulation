from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import scenario, state
from ..db import get_db

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(filter: str = "All", db: Session = Depends(get_db)):
    return state.runs_view(db, filter)


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    r = state.run_detail(db, run_id)
    if not r:
        raise HTTPException(404, "Unknown run")
    return r


@router.post("/{run_id}/start")
async def start_run(run_id: str, db: Session = Depends(get_db)):
    if not state.run_detail(db, run_id):
        raise HTTPException(404, "Unknown run")
    await scenario.start_run(run_id)
    return state.run_detail(db, run_id)


@router.post("/{run_id}/abort")
def abort_run(run_id: str, db: Session = Depends(get_db)):
    return scenario.abort_run(db, run_id)
