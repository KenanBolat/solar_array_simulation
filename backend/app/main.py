import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import orm
from .db import engine, session_scope
from .poller import telemetry_poller
from .routers import racks, units, measurements, alarms, history, runs, scenarios, config
from .seed import seed_if_empty
from .stub_instrument import start_stub_listeners

STUB_PORTS = [5025, 5026]  # matches the seeded demo units' scpi_port


@asynccontextmanager
async def lifespan(app: FastAPI):
    orm.Base.metadata.create_all(engine)
    with session_scope() as db:
        seed_if_empty(db)
    stub_servers = await start_stub_listeners(STUB_PORTS)
    task = asyncio.create_task(telemetry_poller())
    try:
        yield
    finally:
        task.cancel()
        for server in stub_servers:
            server.close()


app = FastAPI(title="Solar Array Simulator Control Platform API", version="0.2.0", lifespan=lifespan)

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
    return {"status": "ok", "mode": "simulation"}
