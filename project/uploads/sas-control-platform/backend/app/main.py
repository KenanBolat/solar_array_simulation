from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import alarms_audit, devices, racks, scenario_runs, scenarios, stream, system
from app.config import settings
from app.logging import configure_logging, correlation_id, get_logger
from app.services.telemetry import telemetry_loop

log = get_logger("main")
_bg_telemetry = settings.environment == "development"  # in-process sampler for dev


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging("DEBUG" if settings.debug else "INFO")
    stop = asyncio.Event()
    task = None
    if _bg_telemetry:
        task = asyncio.create_task(telemetry_loop(stop))
        log.info("started in-process telemetry sampler (dev)")
    log.info("%s up | simulation_mode=%s", settings.app_name, not settings.hardware_enabled)
    try:
        yield
    finally:
        stop.set()
        if task:
            task.cancel()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    cid = request.headers.get("X-Correlation-Id", uuid.uuid4().hex[:16])
    token = correlation_id.set(cid)
    try:
        resp = await call_next(request)
    finally:
        correlation_id.reset(token)
    resp.headers["X-Correlation-Id"] = cid
    return resp


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


for r in (system.router, racks.router, devices.router, scenarios.router,
          scenario_runs.router, alarms_audit.router, stream.router):
    app.include_router(r)
