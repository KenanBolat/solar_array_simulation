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
- `9018-03618.pdf` — **Keysight Series E4360 Programmer's Reference Guide** (E4360-90902, Ed. 3). Every SCPI
  mnemonic, parameter form, response format and error code the backend uses is taken from this document.

---

## Implementation

The design above has been implemented as a real full-stack application that
**controls and reads Keysight E4360-series Solar Array Simulators over SCPI**.

### How a command travels

```
Browser (front panel / safe controls / terminal / scenario)
  │  HTTP POST, JSON            e.g. POST /api/units/SAS-01/setpoint {"voltage": 12}
  ▼
FastAPI  backend/app/routers/units.py
  │  builds the documented program message for that unit's channel
  ▼
backend/app/scpi.py  (pyvisa, pure-python backend)
  │  VOLT 12,(@1)                       ← the command
  │  *OPC?            → 1               ← wait until the instrument has finished
  │  SYST:ERR?        → +0,"No error"   ← did it accept it? (drains the FIFO; first error wins)
  │  VOLT? (@1)       → +1.200000E+01   ← readback, compared with what was commanded
  ▼
CommandHistoryRow: status OK | ERR | UNREACHABLE | TIMEOUT, latency, the exact SCPI text,
the response, and the instrument's error code/message when it refused. Only after OK is
the unit row updated — the instrument is the source of truth, the database is a mirror.
```

Every second the poller (`app/poller.py`) asks each *enabled* unit
`MEAS:VOLT? (@n);:FETC:CURR? (@n);:OUTP? (@n);:CURR:MODE? (@n);:STAT:QUES:COND? (@n)`
(one round trip: a fresh V/I acquisition, output state, operating mode, protection
status) and, in FIXed mode, `VOLT? (@n);:CURR? (@n)`. Whatever comes back overwrites
the cached unit state — so if someone changes the instrument from its physical front
panel, the web UI follows within a second. No valid reply → the unit is *unreachable*,
its readings are **null** (never a made-up number), and any command to it is logged
`UNREACHABLE` and rejected. A reachable, de-energised output legitimately reads `0.0`,
which is a different thing, and the schema keeps them distinct. Protection bits from
`STAT:QUES:COND?` (OV, OC, OT, PF, …) raise alarms when they latch and retire them
when they clear; `OUTP:PROT:CLE (@n)` is available from the front-panel menu.

**Testing the backend directly** (it's plain JSON over HTTP; Swagger UI at
`http://localhost:8000/docs`):

```bash
curl -X POST localhost:8000/api/units/SAS-01/setpoint -H 'Content-Type: application/json' -d '{"voltage": 12}'
curl -X POST localhost:8000/api/units/SAS-01/mode     -H 'Content-Type: application/json' -d '{"mode": "SAS"}'
curl -X POST localhost:8000/api/units/SAS-01/setpoint -H 'Content-Type: application/json' -d '{"voltage": 20}'
#  → 502 {"detail":"set_voltage · rejected by instrument · 315,\"Settings conflict error\" · corr CMD-9F0B"}
curl 'localhost:8000/api/history?filter=All&limit=5'   # the audit rows, with scpi / resp / errCode / err
```

### Units, channels and transports

A **unit** is one output channel (`(@1)` or `(@2)`) of one E4360 mainframe at one IP.
Units are configured from Configuration → Simulator Units (add / delete / enable /
disable / edit addressing) with:

- **IP address** — the mainframe's LAN address.
- **Transport** — `vxi11` (default): VISA `TCPIP0::<ip>::INSTR`, the LAN interface the
  Programmer's Reference documents. `socket`: the same SCPI over a plain TCP port
  (`TCPIP0::<ip>::<port>::SOCKET`). A fixed SCPI socket port is **not** documented in
  this guide, so only choose it if your instrument's LAN configuration page confirms it.
- **Port** — used by the socket transport only.
- **Channel** — 1 or 2.
- **MAC address** — a label for your inventory; not used for communication.

Platform-level soft limits (32 V / 6 A, `data.OPERATIONAL_LIMITS`) are enforced before a
command is sent; the instrument enforces its own module ratings on top.

### Operating modes and "Apply Solar Profile"

`CURR:MODE FIX|SAS,(@n)` selects how the channel behaves. In **FIX** mode the output is
a fixed rectangular V/I characteristic set by `VOLT`/`CURR`. In **SAS** mode it follows
an exponential solar-array I-V curve programmed by four coupled parameters — the
platform sends them in one message so the instrument validates the curve as a whole:
`CURR:SAS:ISC 4.6,(@1);IMP 4.2,(@1);:VOLT:SAS:VMP 28,(@1);VOC 32,(@1)`. In SAS mode a
plain `VOLT`/`CURR` is rejected with `315 Settings conflict error` — the UI warns about
this and the rejection is shown verbatim. Profiles live in `data.SAS_PROFILES`.

### Bundled emulators (no hardware needed)

`backend/app/emulator.py` is a software E4360 mainframe: it parses the same bytes the
driver would send to a physical unit — channel lists, implied header paths in compound
messages, long/short mnemonics, `*OPC?`, the `SYST:ERR?` FIFO with the guide's error
codes — and answers in the same formats, with FIX/SAS physics against a resistive load
and OVP/OCP latching into `STAT:QUES:COND?`. Two instances start with the backend on
`127.0.0.1:5025` / `:5026`; the seeded units **SAS-01** and **SAS-02** point at them
(transport `socket`). To drive your physical units, edit each unit's IP and switch the
transport to `vxi11` in Configuration — the driver code path is identical.

### Run it

```bash
# backend (http://localhost:8000)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # includes pyvisa + pyvisa-py
.venv/bin/python -m uvicorn app.main:app --port 8000

# frontend (http://localhost:3301) — proxies /api/* to the backend above
cd frontend
npm install
npm run dev
```

Then open http://localhost:3301.

If you already have a `backend/data.db` from an earlier version, delete it — the schema
changed (channel/transport columns, mirrored instrument state, richer audit rows) and
there's no migration system yet:

```bash
rm backend/data.db   # fresh schema + seed on next start
```

### What is still simulated

- The **scenario runner** walks the Eclipse Cycle steps as a timed sequence and records
  events, but does not yet dispatch each step to the instrument. Note the sample
  scenario's "Set Voltage" step is only valid in FIX mode — after "Apply Solar Profile"
  (SAS mode) a real instrument would answer 315; the step order needs revisiting before
  live per-step dispatch.
- The 24 h of measurement history seeded on first start is synthetic (so charts aren't
  empty); everything from that moment on is real polled data.
- Save / Validate / Dry Run in the Scenario Builder are placeholders.

### Offline

Fonts (IBM Plex Sans/Mono) are self-hosted under `frontend/public/fonts/` and
loaded via local `@font-face` rules in `app/globals.css` — no `next/font/google`
and no Google Fonts `<link>`. The frontend dev server and the running app need
no internet access at all.
