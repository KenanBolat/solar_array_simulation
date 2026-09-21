#!/usr/bin/env bash
# Start the platform the way it should be served to other people: the backend,
# and a PRODUCTION frontend build.
#
# `npm run dev` is deliberately not used here. The dev server opens a hot-reload
# WebSocket back to whichever host the page was loaded from, which fails on a LAN
# and fills every tester's console with ERR_CONNECTION_RESET. The production
# build opens no WebSocket at all.
#
#   ./serve.sh                       real instruments, from backend/fleet.json
#   ./serve.sh --emulator            the two bundled software mainframes
#
set -euo pipefail
cd "$(dirname "$0")"

FLEET=""
[[ "${1:-}" == "--emulator" ]] && FLEET="fleet.emulator.json"

if [[ ! -x backend/.venv/bin/python ]]; then
  echo "backend/.venv missing — run:" >&2
  echo "  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

cleanup() { [[ -n "${BACK_PID:-}" ]] && kill "$BACK_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "→ backend on :8000${FLEET:+  (fleet $FLEET)}"
( cd backend && SAS_FLEET_FILE="$FLEET" .venv/bin/python -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 ) &
BACK_PID=$!

# Wait for it rather than racing the frontend's first proxied request.
for _ in $(seq 1 40); do
  curl -sf -o /dev/null http://localhost:8000/api/health && break
  sleep 0.5
done

cd frontend
[[ -d node_modules ]] || npm install
echo "→ building the frontend (no hot-reload socket, unlike npm run dev)"
npm run build
echo "→ frontend on :3301 — open http://$(hostname -I 2>/dev/null | awk '{print $1}'):3301"
exec npm start
