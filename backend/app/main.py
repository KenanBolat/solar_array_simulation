from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import racks, units, measurements, alarms, history, runs, scenarios, config

app = FastAPI(title="Solar Array Simulator Control Platform API", version="0.1.0")

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
