# API Reference

Base URL (dev): `http://localhost:8000`. Interactive OpenAPI docs are served at
`/docs` when the API is running.

## Authentication

During development the API trusts the `X-Dev-User` header to impersonate a
seeded user (`observer`, `operator`, `supervisor`, `administrator`). With no
header it defaults to the view-only `observer`. In production this is replaced
by a real identity provider; the permission checks behind it are unchanged.

Permissions by role:

| Permission | observer | operator | supervisor | administrator |
|---|:--:|:--:|:--:|:--:|
| `view` | ✓ | ✓ | ✓ | ✓ |
| `run_scenario` | | ✓ | ✓ | ✓ |
| `control_output` | | ✓ | ✓ | ✓ |
| `approve_scenario` | | | ✓ | ✓ |
| `admin` | | | | ✓ |

## System

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/health` | — | Liveness. |
| GET | `/ready` | — | Readiness (DB reachable). |
| GET | `/api/meta` | — | App name, `simulation_mode`, `hardware_enabled`, capability map version, soft limits. |
| GET | `/metrics` | — | Prometheus exposition. |

## Topology

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/racks` | view | List racks. |
| GET | `/api/racks/{rack_id}` | view | Rack with nested mainframes → modules → channels. |
| GET | `/api/devices` | view | List devices; optional `?rack_id=`. Includes cached `last_state`. |
| GET | `/api/devices/{id}` | view | One device with connection profile. |
| GET | `/api/devices/{id}/state` | view | Live state snapshot (`simulation` flag included). |
| GET | `/api/devices/{id}/capabilities` | view | Validated command templates for the device. |
| GET | `/api/devices/{id}/measurements?window=5m\|30m\|1h\|24h` | view | Time-series rows. |
| GET | `/api/devices/{id}/measurements.csv?window=…` | view | CSV export. |

## Control (audited)

| Method | Path | Permission | Notes |
|---|---|---|---|
| POST | `/api/devices/{id}/commands` | control_output | Body `{template_id, params, confirmed}`. Hazardous templates return **428** if `confirmed` is false. |
| POST | `/api/devices/{id}/output` | control_output | Body `{enabled, confirmed}`. |
| POST | `/api/devices/{id}/safe-shutdown` | control_output | Disable output and bring the unit to a safe state. |

A command response includes `status`, `scpi_sent`, `scpi_response`,
`readback_verified`, `latency_ms`, and timestamps.

## Scenarios

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/scenarios` | view | List scenarios. |
| GET | `/api/scenarios/{id}` | view | Scenario detail with nodes/edges and status. |
| POST | `/api/scenarios` | run_scenario | Create a scenario (draft) from nodes/edges. |
| POST | `/api/scenarios/{id}/validate` | run_scenario | Returns `{valid, errors[], warnings[]}`. |
| POST | `/api/scenarios/{id}/approve` | approve_scenario | Validates then marks the version approved. |
| POST | `/api/scenarios/{id}/run` | run_scenario | Body `{target_device_ids, dry_run, confirmed}`. |

## Scenario runs

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/scenario-runs` | view | List runs with progress. |
| GET | `/api/scenario-runs/{id}` | view | One run. |
| GET | `/api/scenario-runs/{id}/events` | view | Ordered run event log. |
| POST | `/api/scenario-runs/{id}/pause` | run_scenario | |
| POST | `/api/scenario-runs/{id}/resume` | run_scenario | |
| POST | `/api/scenario-runs/{id}/abort` | run_scenario | |

## Alarms & audit

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/api/alarms?active_only=…&device_id=…` | view | List alarms. |
| POST | `/api/alarms/{id}/ack` | control_output | Acknowledge. |
| GET | `/api/audit-log?device_id=…&limit=…` | view | Append-only audit trail (≤2000). |

## Live streams (SSE)

`GET /api/stream/{channel}` where channel ∈ `measurements`, `device_state`,
`command_status`, `alarms`, `scenario_progress`. Each message is a named SSE
event whose `data` is a JSON payload. The browser uses `EventSource`; if the
stream drops, the UI's background polling keeps state current.
