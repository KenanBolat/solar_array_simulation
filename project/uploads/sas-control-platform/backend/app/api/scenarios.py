from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.metrics import scenario_runs_total
from app.models import Scenario, ScenarioEdge, ScenarioNode, ScenarioRun, ScenarioVersion
from app.schemas.scenarios import (
    EdgeIn,
    NodeIn,
    RunIn,
    RunOut,
    ScenarioDetailOut,
    ScenarioIn,
    ScenarioOut,
    ValidationOut,
)
from app.security import Principal, require
from app.services.scenario_engine import execute_run
from app.services.scenario_validation import validate_scenario

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _utcnow():
    return datetime.now(UTC)


async def _latest_version(session, scenario_id) -> ScenarioVersion | None:
    return (await session.execute(
        select(ScenarioVersion).where(ScenarioVersion.scenario_id == scenario_id)
        .order_by(ScenarioVersion.version.desc()))).scalars().first()


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(session: AsyncSession = Depends(get_session),
                         _=Depends(require("view"))):
    return (await session.execute(select(Scenario).order_by(Scenario.name))).scalars().all()


@router.get("/{scenario_id}", response_model=ScenarioDetailOut)
async def get_scenario(scenario_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                       _=Depends(require("view"))):
    s = (await session.execute(select(Scenario).where(Scenario.id == scenario_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "scenario not found")
    v = await _latest_version(session, scenario_id)
    nodes = [NodeIn(node_key=n.node_key, type=n.type, label=n.label, x=n.x, y=n.y, config=n.config)
             for n in (v.nodes if v else [])]
    edges = [EdgeIn(edge_key=e.edge_key, source=e.source, target=e.target, label=e.label)
             for e in (v.edges if v else [])]
    return ScenarioDetailOut(id=s.id, name=s.name, description=s.description,
                             current_version=s.current_version,
                             status=v.status if v else "draft", nodes=nodes, edges=edges)


@router.post("", response_model=ScenarioOut)
async def create_scenario(body: ScenarioIn,
                          principal: Principal = Depends(require("run_scenario")),
                          session: AsyncSession = Depends(get_session)):
    s = Scenario(name=body.name, description=body.description, current_version=1)
    session.add(s)
    await session.flush()
    v = ScenarioVersion(scenario_id=s.id, version=1, status="draft")
    session.add(v)
    await session.flush()
    for n in body.nodes:
        session.add(ScenarioNode(version_id=v.id, node_key=n.node_key, type=n.type,
                                 label=n.label, x=n.x, y=n.y, config=n.config))
    for e in body.edges:
        session.add(ScenarioEdge(version_id=v.id, edge_key=e.edge_key, source=e.source,
                                 target=e.target, label=e.label))
    await session.commit()
    return s


@router.post("/{scenario_id}/validate", response_model=ValidationOut)
async def validate(scenario_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                   _=Depends(require("run_scenario"))):
    v = await _latest_version(session, scenario_id)
    if not v:
        raise HTTPException(404, "no version to validate")
    nodes = [{"node_key": n.node_key, "type": n.type, "config": n.config} for n in v.nodes]
    edges = [{"source": e.source, "target": e.target} for e in v.edges]
    r = validate_scenario(nodes, edges)
    if r.valid and v.status == "draft":
        v.status = "validated"
        await session.commit()
    return ValidationOut(valid=r.valid, errors=r.errors, warnings=r.warnings)


@router.post("/{scenario_id}/approve", response_model=ValidationOut)
async def approve(scenario_id: uuid.UUID,
                  principal: Principal = Depends(require("approve_scenario")),
                  session: AsyncSession = Depends(get_session)):
    v = await _latest_version(session, scenario_id)
    if not v:
        raise HTTPException(404, "no version")
    if v.status not in ("validated", "approved"):
        raise HTTPException(409, "scenario must be validated before approval")
    v.status = "approved"
    v.approved_by = principal.username
    await session.commit()
    return ValidationOut(valid=True, errors=[], warnings=[])


@router.post("/{scenario_id}/run", response_model=RunOut)
async def run_scenario(scenario_id: uuid.UUID, body: RunIn, bg: BackgroundTasks,
                       principal: Principal = Depends(require("run_scenario")),
                       session: AsyncSession = Depends(get_session)):
    s = (await session.execute(select(Scenario).where(Scenario.id == scenario_id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "scenario not found")
    v = await _latest_version(session, scenario_id)
    nodes = [{"node_key": n.node_key, "type": n.type, "config": n.config} for n in v.nodes]
    edges = [{"source": e.source, "target": e.target} for e in v.edges]
    chk = validate_scenario(nodes, edges)
    if not chk.valid:
        raise HTTPException(422, {"message": "scenario invalid", "errors": chk.errors})
    # live runs require an approved version
    if not body.dry_run and v.status != "approved":
        raise HTTPException(409, "live run requires an approved scenario version")

    run = ScenarioRun(scenario_id=scenario_id, version=v.version, status="pending",
                      dry_run=body.dry_run, target_device_ids=[str(x) for x in body.target_device_ids],
                      started_by=principal.username)
    session.add(run)
    await session.commit()
    scenario_runs_total.labels("pending").inc()
    full_nodes = [{"node_key": n.node_key, "type": n.type, "config": n.config,
                   "label": n.label} for n in v.nodes]
    bg.add_task(execute_run, run.id, full_nodes, edges, principal.username)
    return run
