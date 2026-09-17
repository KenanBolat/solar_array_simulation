import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import orm
from .db import engine, ensure_columns, session_scope
from .diagnostics import host_addresses
from .emulator import demo_emulators
from .poller import telemetry_poller
from .routers import racks, units, measurements, alarms, history, runs, scenarios, config
from .seed import FLEET_FILE, is_loopback, seed_if_empty

EMULATORS = demo_emulators()  # 127.0.0.1:5025 / :5026 — started only when something is addressed at loopback


def _emulators_wanted() -> bool:
    if os.environ.get("SAS_EMULATORS", "").lower() in ("1", "true", "yes"):
        return True
    with session_scope() as db:
        return any(is_loopback(u.ip_address) for u in db.query(orm.Unit).all())


@asynccontextmanager
async def lifespan(app: FastAPI):
    orm.Base.metadata.create_all(engine)
    ensure_columns(orm.Base)
    with session_scope() as db:
        seed_if_empty(db)
    servers = []
    if _emulators_wanted():
        servers = [s for s in [await e.serve() for e in EMULATORS] if s]
    task = asyncio.create_task(telemetry_poller())
    try:
        yield
    finally:
        task.cancel()
        for server in servers:
            server.close()


app = FastAPI(title="Solar Array Simulator Control Platform API", version="0.4.0", lifespan=lifespan)

# The UI is served to the whole lab LAN from one host; it reaches this API
# through the Next.js proxy (same origin) or directly. No cookies/credentials
# are used, so any origin may call it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (racks.router, units.router, measurements.router, alarms.router,
          history.router, runs.router, scenarios.router, config.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    with session_scope() as db:
        n = db.query(orm.Unit).count()
        emulated = sum(1 for u in db.query(orm.Unit).all() if is_loopback(u.ip_address))
    return {"status": "ok", "mode": "live-scpi", "fleetFile": str(FLEET_FILE), "units": n,
            "emulatedUnits": emulated, "emulators": [e.port for e in EMULATORS] if emulated else [],
            "host": host_addresses(), "uiPort": 3301}
