from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import state
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
    r = state.run_detail(db, run_id)
    if not r:
        raise HTTPException(404, "Unknown run")
    await state.start_run(run_id)
    return state.run_detail(db, run_id)


@router.post("/{run_id}/pause")
def pause_run(run_id: str, db: Session = Depends(get_db)):
    return state.pause_run(db, run_id)


@router.post("/{run_id}/abort")
def abort_run(run_id: str, db: Session = Depends(get_db)):
    return state.abort_run(db, run_id)
