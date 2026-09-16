# Solar Array Simulator Control Platform

An on-premise, safety-aware web platform to **monitor and control a fleet of
Keysight E4360A Solar Array Simulator units over SCPI** — running today, end to
end, against a mock instrument layer. Real hardware is kept behind a single
master switch that is **off by default**, and the whole UI is labelled
**SIMULATION MODE** until that switch is deliberately enabled.

This is a runnable MVP, not a mockup: a typed FastAPI backend with a real
PostgreSQL/TimescaleDB schema and migrations, an instrument-driver abstraction
with a full synthetic E4360A, a Next.js operator console with ten working
modules, live telemetry over SSE, a visual scenario builder, observability, and
tests.

> ⚠️ **Safety first.** Every instrument runs through the mock driver until
> `SAS_HARDWARE_ENABLED=true`. Before connecting real hardware, work through
> [`docs/HARDWARE_INTEGRATION.md`](docs/HARDWARE_INTEGRATION.md) — in particular,
> **no manufacturer SCPI command is assumed correct**; only `*IDN?` is treated as
> verified and everything else must be confirmed against the official Keysight
> E4360 programming manual.

## Quickstart

```bash
# from the repository root
docker compose up --build
```

Then open:

- **Console:** http://localhost:3000
- **API + OpenAPI docs:** http://localhost:8000/docs
- **Metrics:** http://localhost:8000/metrics

The stack seeds **3 racks / 20 units** and one approved example scenario on
first start. Live simulated telemetry flows immediately. Use the **role selector**
in the sidebar to exercise RBAC (observer → operator → supervisor → administrator).

Optional profiles:

```bash
docker compose --profile workers up --build         # telemetry in its own process
docker compose --profile observability up --build   # + Prometheus (9090) & Grafana (3001)
```

### Running locally without Docker

Backend (Python 3.13):

```bash
cd backend
pip install -r requirements.txt
# point at a local Postgres+TimescaleDB, then:
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload
```

Frontend (Node 22):

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## Tests

```bash
cd backend && pytest                # 23 unit tests pass; DB-backed integration tests skip without a DB
cd frontend && npm run typecheck && npm run build
cd e2e && npm install && npx playwright install && npm test   # against a running stack
```

## The ten console modules

Overview dashboard · Rack Explorer · Simulator Control (per-unit console) ·
Measurements · Scenario Builder · Scenario Runs · Command History ·
Alarms & Events · Device Configuration · Administration.

The signature element is the **rack rendered as physical 1U bays**, each lit by
its unit's live state and clickable straight into the control console.

## Architecture in one paragraph

A FastAPI service exposes REST + SSE + Prometheus metrics. Commands flow through
a **per-instrument command queue** (never concurrent writes), a command service
that validates parameters, performs **readback verification**, persists an
**append-only audit** entry, and publishes events. An **InstrumentDriver** ABC
sits behind a registry whose master switch chooses the **MockE4360Driver**
(synthetic I-V curve, fault profiles) or the inert real **E4360Driver**. State
lives in PostgreSQL with a **TimescaleDB hypertable** for measurements. The
Next.js console reads via TanStack Query (polling) and SSE (live). Full detail,
the technology rationale, and a Mermaid diagram are in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```
backend/    FastAPI app, drivers, services, models, Alembic migration, seed, worker, tests
frontend/   Next.js App Router console (10 modules), design system, lib (api/hooks/sse/store)
e2e/        Playwright smoke tests for the safety-critical flows
observability/  Prometheus scrape config + Grafana datasource & dashboard
docs/       ARCHITECTURE · API · HARDENING · HARDWARE_INTEGRATION
docker-compose.yml   db · redis · api · frontend (+ worker / observability profiles)
```

## Deliverables map

| # | Deliverable | Where |
|---|---|---|
| 1 | Architecture & explicit assumptions | `docs/ARCHITECTURE.md` §1 |
| 2 | Technology selection + justification | `docs/ARCHITECTURE.md` §2 |
| 3 | System diagram (Mermaid) | `docs/ARCHITECTURE.md` §3 |
| 4 | Repository structure | this file + the tree above |
| 5 | DB schema + migration strategy | `backend/app/models/*`, `backend/alembic/`, `backend/app/timescale.py` |
| 6 | API design | `docs/API.md`, `backend/app/api/*` |
| 7 | Frontend screens | `frontend/app/*` (ten modules) |
| 8 | Working MVP code | entire repo (backend tested, frontend builds) |
| 9 | Docker Compose deployment | `docker-compose.yml` |
| 10 | Seed data — 3 racks / 20 units | `backend/app/seed.py` |
| 11 | Example scenario | seeded "approved" scenario; edit in Scenario Builder |
| 12 | Unit + e2e tests | `backend/tests/*`, `e2e/tests/*` |
| 13 | Run instructions | this file |
| 14 | Production hardening checklist | `docs/HARDENING.md` |
| 15 | Info needed before real hardware | `docs/HARDWARE_INTEGRATION.md` |

## What is production-deep vs scaffolded (honest scope)

**Built through:** the driver abstraction + mock + registry master switch; the
command queue, validation, readback, and append-only audit; the relational +
TimescaleDB schema with a working migration and seed; RBAC with four roles;
scenario validation (rejecting unbounded loops/retries, unknown nodes, offline
targets) and a run interpreter; the full ten-module UI; SSE live channels with
polling fallback; Prometheus metrics + a Grafana dashboard.

**Deliberately scaffolded for the MVP** (and listed in `docs/HARDENING.md`):
authentication is a dev header rather than SSO/JWT; the event bus is in-process
(Redis fan-out is interfaced but not wired, so cross-process SSE needs the
hardening step); the real SCPI strings are placeholders pending manual
verification; TLS/CSP, secret management, and backup/restore are deployment
concerns left to the target environment.

**Air-gapped note.** Nothing in the build or runtime reaches the public
internet. The UI uses system font fallbacks; to ship the exact Inter / JetBrains
Mono faces in a sealed network, vendor the `.woff2` files and load them with
`next/font/local` (a drop-in change in `frontend/app/layout.tsx`). Images are
pinned and can be moved with `docker save` / `docker load`.
