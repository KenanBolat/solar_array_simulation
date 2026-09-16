from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ScenarioRun, ScenarioRunEvent
from app.schemas.scenarios import RunEventOut, RunOut
from app.security import require
from app.services import scenario_engine

router = APIRouter(prefix="/api/scenario-runs", tags=["scenario-runs"])


@router.get("", response_model=list[RunOut])
async def list_runs(session: AsyncSession = Depends(get_session), _=Depends(require("view"))):
    return (await session.execute(
        select(ScenarioRun).order_by(ScenarioRun.created_at.desc()).limit(100))).scalars().all()


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                  _=Depends(require("view"))):
    r = (await session.execute(select(ScenarioRun).where(ScenarioRun.id == run_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "run not found")
    return r


@router.get("/{run_id}/events", response_model=list[RunEventOut])
async def run_events(run_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                     _=Depends(require("view"))):
    return (await session.execute(
        select(ScenarioRunEvent).where(ScenarioRunEvent.run_id == run_id)
        .order_by(ScenarioRunEvent.ts_utc))).scalars().all()


@router.post("/{run_id}/pause")
async def pause(run_id: uuid.UUID, _=Depends(require("run_scenario"))):
    scenario_engine.request_pause(str(run_id))
    return {"run_id": str(run_id), "status": "pause-requested"}


@router.post("/{run_id}/resume")
async def resume(run_id: uuid.UUID, _=Depends(require("run_scenario"))):
    scenario_engine.request_resume(str(run_id))
    return {"run_id": str(run_id), "status": "resume-requested"}


@router.post("/{run_id}/abort")
async def abort(run_id: uuid.UUID, _=Depends(require("run_scenario"))):
    scenario_engine.request_abort(str(run_id))
    return {"run_id": str(run_id), "status": "abort-requested"}
