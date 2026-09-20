from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
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


@router.get("/{run_id}/export.csv")
def export_run(run_id: str, measured: bool = False, db: Session = Depends(get_db)):
    """The run as a CSV: one row per step, with the SCPI sent, the reply, the
    latency and any reading — ready to chart in Excel. `measured=true` keeps only
    the rows that carry a reading."""
    if not state.run_detail(db, run_id):
        raise HTTPException(404, "Unknown run")
    # utf-8-sig so Excel opens it with the right encoding without an import step
    body = scenario.run_csv_text(db, run_id, measured_only=measured).encode("utf-8-sig")
    name = f"{run_id}{'-measurements' if measured else ''}.csv"
    return Response(body, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/{run_id}/start")
async def start_run(run_id: str, db: Session = Depends(get_db)):
    if not state.run_detail(db, run_id):
        raise HTTPException(404, "Unknown run")
    await scenario.start_run(run_id)
    return state.run_detail(db, run_id)


@router.post("/{run_id}/abort")
def abort_run(run_id: str, db: Session = Depends(get_db)):
    return scenario.abort_run(db, run_id)
