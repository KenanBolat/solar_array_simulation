#!/usr/bin/env bash
# Backend entrypoint.
#   ROLE=api    -> wait for DB, run migrations + seed, then start uvicorn
#   ROLE=worker -> wait for DB + migrations, then start the telemetry worker
# The two roles are coordinated so migrations run exactly once (api owns them).
set -euo pipefail

ROLE="${ROLE:-api}"
HOST="${DB_HOST:-db}"
PORT="${DB_PORT:-5432}"

echo "[entrypoint] role=${ROLE} waiting for database ${HOST}:${PORT} ..."
for _ in $(seq 1 60); do
  if python -c "import socket,sys; s=socket.socket(); s.settimeout(1)
try:
    s.connect(('${HOST}', ${PORT})); s.close()
except Exception: sys.exit(1)" 2>/dev/null; then
    echo "[entrypoint] database is reachable"
    break
  fi
  sleep 1
done

if [ "${ROLE}" = "api" ]; then
  echo "[entrypoint] applying migrations ..."
  alembic upgrade head
  echo "[entrypoint] seeding (idempotent) ..."
  python -m app.seed || echo "[entrypoint] seed step reported a non-fatal issue"
else
  # worker: give the api a moment to finish migrations
  echo "[entrypoint] worker waiting for schema ..."
  for _ in $(seq 1 60); do
    if python -c "
from sqlalchemy import create_engine, text
from app.config import settings
try:
    e=create_engine(settings.database_url_sync)
    with e.connect() as c: c.execute(text('select 1 from racks limit 1'))
except Exception: raise SystemExit(1)
" 2>/dev/null; then
      echo "[entrypoint] schema present"
      break
    fi
    sleep 1
  done
fi

echo "[entrypoint] exec: $*"
exec "$@"
