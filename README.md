# CODING AGENTS: READ THIS FIRST

This is a **handoff bundle** from Claude Design (claude.ai/design).

A user mocked up designs in HTML/CSS/JS using an AI design tool, then exported this bundle so a coding agent can implement the designs for real.

## What you should do — IMPORTANT

**Read the chat transcripts first.** There are 1 chat transcript(s) in `chats/`. The transcripts show the full back-and-forth between the user and the design assistant — they tell you **what the user actually wants** and **where they landed** after iterating. Don't skip them. The final HTML files are the output, but the chat is where the intent lives.

**Read `project/Solar Array Simulator Control.dc.html` in full.** The user had this file open when they triggered the handoff, so it's almost certainly the primary design they want built. Read it top to bottom — don't skim. Then **follow its imports**: open every file it pulls in (shared components, CSS, scripts) so you understand how the pieces fit together before you start implementing.

**If anything is ambiguous, ask the user to confirm before you start implementing.** It's much cheaper to clarify scope up front than to build the wrong thing.

## About the design files

The design medium is **HTML/CSS/JS** — these are prototypes, not production code. Your job is to **recreate them pixel-perfectly** in whatever technology makes sense for the target codebase (React, Vue, native, whatever fits). Match the visual output; don't copy the prototype's internal structure unless it happens to fit.

**Don't render these files in a browser or take screenshots unless the user asks you to.** Everything you need — dimensions, colors, layout rules — is spelled out in the source. Read the HTML and CSS directly; a screenshot won't tell you anything they don't.

## Bundle contents

- `README.md` — this file
- `chats/` — conversation transcripts (read these!)
- `project/` — the `Solar Array Simulator Control Platform` project files (HTML prototypes, assets, components)

---

## Implementation

The design above has been implemented as a real full-stack application:

- `backend/` — FastAPI service backed by **SQLite** (`backend/data.db`, created and
  seeded automatically on first run — see `backend/app/orm.py`/`seed.py`). Units,
  racks, measurements, command-audit log, alarms, and scenario runs are all real
  persisted rows; nothing resets on restart. A background poller (`app/poller.py`)
  runs every second against every *enabled* unit and does two things for real:
  (1) a genuine TCP connect probe to the unit's `ip_address:scpi_port` — no SCPI
  sent, just "does anything answer" — which sets `online`, and (2) writes one
  measurement row per unit: a computed reading if reachable, or an explicit null
  if not. A de-energised-but-reachable output legitimately reads `0.0`, which is
  not the same thing as "no reading," and the schema keeps them distinct.
  Measurement *values* are still simulated (no verified SCPI query syntax exists
  for this instrument — see below), but reachability is real: if the machine
  running the backend can't route to the instrument's IP, the unit correctly
  shows unreachable and every field goes null, exactly like a real outage would.
  Default seed topology is a single RACK-A with two units: **SAS-01** (active,
  output on) and **SAS-02** (standby, output off). Units are addressed by
  **IP + MAC** (+ a configurable SCPI port, default `5025` — unconfirmed for
  this instrument); the VISA resource string (`TCPIP0::<ip>::inst0::INSTR`) is
  derived automatically and isn't user-facing. Units can be added, deleted,
  enabled/disabled, and had their network info edited from Configuration →
  Simulator Units. No real SCPI driver — measurement retrieval is a simulation
  only, by design (see the handoff conversation in `chats/`); the attached
  E4360 manual turned out to be the Service Guide, not the Programming Guide,
  so it doesn't cover LAN/SCPI addressing — that's needed before real
  measurement commands can be added.

  **About the seeded IPs.** SAS-01/SAS-02 ship pointed at `127.0.0.1:5025` /
  `127.0.0.1:5026` — a tiny local TCP listener (`app/stub_instrument.py`,
  started by the backend on boot) that exists solely so the *real*
  reachability probe has something genuine to connect to out of the box. It
  doesn't speak SCPI or anything else; it only accepts the TCP handshake.
  This isn't a fake reachability signal — the socket connection really
  happens — it's just a stand-in target instead of the physical instruments.
  Their real MACs (`80-09-02-05-6A-48` / `80-09-02-08-16-C4`) are kept as
  labels. Once you're running the backend on a host with LAN access to the
  actual E4360A units, repoint each one's IP (and port, if different) at the
  real device from Configuration → Simulator Units — from that point on,
  reachability and the online/offline state reflect the real instrument, not
  the stub.
- `frontend/` — Next.js (App Router) + TypeScript + Tailwind app implementing all
  nine screens from the wireframe: Intro, Rack Overview, Simulator Control (with
  Virtual Front Panel and guided Command Terminal modals), Measurements, Scenario
  Runs, Command History, Alarms, Configuration (incl. drag-and-drop rack editor),
  and the Scenario Builder canvas.

### Run it

```bash
# backend (http://localhost:8000)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8000

# frontend (http://localhost:3301) — proxies /api/* to the backend above
cd frontend
npm install
npm run dev
```

Then open http://localhost:3301.

If you already have a `backend/data.db` from before this change, delete it —
the schema changed (new columns, nullable measurements) and there's no
migration system yet:

```bash
rm backend/data.db   # fresh schema + seed (real IPs/MACs) on next start
```

### Offline

Fonts (IBM Plex Sans/Mono) are self-hosted under `frontend/public/fonts/` and
loaded via local `@font-face` rules in `app/globals.css` — no `next/font/google`
and no Google Fonts `<link>`. The frontend dev server and the running app need
no internet access at all.
