import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import orm
from .db import engine, ensure_columns, session_scope
from .emulator import demo_emulators
from .poller import telemetry_poller
from .routers import racks, units, measurements, alarms, history, runs, scenarios, config
from .seed import seed_if_empty

EMULATORS = demo_emulators()  # 127.0.0.1:5025 and :5026 — the seeded demo units point here


@asynccontextmanager
async def lifespan(app: FastAPI):
    orm.Base.metadata.create_all(engine)
    ensure_columns(orm.Base)
    with session_scope() as db:
        seed_if_empty(db)
    servers = [s for s in [await e.serve() for e in EMULATORS] if s]
    task = asyncio.create_task(telemetry_poller())
    try:
        yield
    finally:
        task.cancel()
        for server in servers:
            server.close()


app = FastAPI(title="Solar Array Simulator Control Platform API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3301"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (racks.router, units.router, measurements.router, alarms.router,
          history.router, runs.router, scenarios.router, config.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "live-scpi", "emulators": [e.port for e in EMULATORS]}
