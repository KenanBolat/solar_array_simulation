# Production Hardening Checklist

This is the MVP's honest gap list. The application is structured so each item
below is an addition at a boundary, not a rewrite. Items are grouped and ordered
roughly by priority for a defense/aerospace on-premise deployment.

## Authentication & authorization
- [ ] Replace dev-auth (`X-Dev-User`) with a real identity provider (SSO/OIDC or
      mTLS client certs). Disable `SAS_DEV_AUTH_ENABLED`.
- [ ] Map directory groups to the existing roles (`observer`/`operator`/
      `supervisor`/`administrator`); the permission checks do not change.
- [ ] Enforce short-lived tokens; carry the authenticated identity into SSE
      (signed cookie or token in the EventSource URL via a short-lived ticket).
- [ ] Add per-action re-authentication (step-up) for output enable and shutdown.

## Transport & network
- [ ] Terminate TLS at a reverse proxy; HSTS; internal-only certificate chain.
- [ ] Lock CORS to the exact console origin(s); remove localhost defaults.
- [ ] Place the instrument network on its own VLAN; the API host is the only
      route to it. No browser-reachable path to instruments.
- [ ] Rate-limit control endpoints; size SSE connection limits.

## Instrument safety
- [ ] Complete `docs/HARDWARE_INTEGRATION.md` and verify **every** SCPI string
      against the Keysight E4360 programming manual before enabling hardware.
- [ ] Keep `SAS_HARDWARE_ENABLED=false` until a documented commissioning sign-off.
- [ ] Confirm hardware over-voltage/over-current protection is set on the
      instruments themselves; treat app soft limits as advisory only.
- [ ] Add an interlock check (and physical E-stop wiring confirmation) before any
      output-enable path is allowed in production.
- [ ] Verify the per-instrument command queue under real VISA latency and add a
      hard command timeout with a safe-state fallback.

## Data & state
- [ ] Externalize secrets (DB, Redis) to a secret manager; rotate.
- [ ] Turn on TimescaleDB compression in addition to retention; size chunks.
- [ ] Back up PostgreSQL (PITR) and test restore; the audit log is a record of
      operator actions and must be durable and tamper-evident.
- [ ] Move the event bus to Redis (pub/sub) so SSE fans out across API replicas
      and the telemetry worker; the interface is already in place.

## Reliability & scale
- [ ] Run the telemetry worker as its own process (the `workers` compose
      profile) and the API stateless behind a load balancer.
- [ ] Add liveness/readiness to orchestration; graceful shutdown drains the
      command queue and SSE connections.
- [ ] Connection pooling sized to instrument count; backpressure on the queue.

## Observability & audit
- [ ] Ship JSON logs with correlation IDs to a central store; retain per policy.
- [ ] Alert on `sas_active_alarms`, failed-command rate, and telemetry write
      stalls (dashboards provided under `observability/`).
- [ ] Add an immutable audit export (e.g. WORM storage) for compliance.

## Supply chain & build
- [ ] Pin and scan all images; vendor them via `docker save`/`docker load` for
      the air-gapped target.
- [ ] Vendor the exact UI fonts with `next/font/local` (see README) so the build
      is byte-reproducible offline.
- [ ] Generate an SBOM; verify no build/runtime path reaches the public internet.

## Frontend
- [ ] Add a Content-Security-Policy; subresource integrity where applicable.
- [ ] Replace the dev role switcher with the authenticated identity.
- [ ] Add error boundaries and an offline/degraded banner when the API is
      unreachable.
