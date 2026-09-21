import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import (get_redoc_html, get_swagger_ui_html,
                                  get_swagger_ui_oauth2_redirect_html)
from fastapi.staticfiles import StaticFiles

from . import orm, scenario, state
from .db import backfill_defaults, engine, ensure_columns, session_scope
from .diagnostics import host_addresses
from .emulator import demo_emulators
from .poller import telemetry_poller
from .routers import racks, units, measurements, alarms, history, runs, scenarios, config, presets
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
    backfill_defaults()
    with session_scope() as db:
        seed_if_empty(db)
        state.seed_presets(db)
        scenario.seed_default(db)
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


# FastAPI's built-in /docs and /redoc load Swagger UI and ReDoc from jsdelivr and
# their favicon from fastapi.tiangolo.com. The lab host has no internet, so those
# requests fail and the page renders blank ("SwaggerUIBundle is not defined").
# The bundles are vendored under app/static/docs and served from this host
# instead; docs_url/redoc_url are disabled so the routes below replace them.
DOCS_DIR = Path(__file__).resolve().parent / "static" / "docs"

app = FastAPI(title="Solar Array Simulator Control Platform API", version="0.4.0", lifespan=lifespan,
              docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=DOCS_DIR.parent), name="static")


# Both pages must work with no route off this host. The policy enforces that:
# anything either bundle still tries to fetch from the internet (ReDoc pulls a
# decorative logo from cdn.redoc.ly) is blocked by the browser instead of
# hanging until it times out. 'unsafe-inline' is required by the bundles' own
# bootstrap script and styles.
OFFLINE_CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; "
               "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
               "font-src 'self' data:; connect-src 'self'; "
               # ReDoc parses the schema in a worker it creates from a blob; without
               # this it falls back to script-src and the worker is refused.
               "worker-src 'self' blob:")


def _offline(response: HTMLResponse) -> HTMLResponse:
    response.headers["Content-Security-Policy"] = OFFLINE_CSP
    return response


@app.get("/docs", include_in_schema=False)
def swagger_ui():
    return _offline(get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/static/docs/swagger-ui-bundle.js",
        swagger_css_url="/static/docs/swagger-ui.css",
        swagger_favicon_url="/static/docs/favicon.png",
    ))


@app.get(app.swagger_ui_oauth2_redirect_url or "/docs/oauth2-redirect", include_in_schema=False)
def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
def redoc():
    return _offline(get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — ReDoc",
        redoc_js_url="/static/docs/redoc.standalone.js",
        redoc_favicon_url="/static/docs/favicon.png",
        with_google_fonts=False,   # ReDoc otherwise pulls Montserrat/Roboto from Google
    ))

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
          history.router, runs.router, scenarios.router, config.router, presets.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    with session_scope() as db:
        n = db.query(orm.Unit).count()
        emulated = sum(1 for u in db.query(orm.Unit).all() if is_loopback(u.ip_address))
    return {"status": "ok", "mode": "live-scpi", "fleetFile": str(FLEET_FILE), "units": n,
            "emulatedUnits": emulated, "emulators": [e.port for e in EMULATORS] if emulated else [],
            "host": host_addresses(), "uiPort": 3301}
