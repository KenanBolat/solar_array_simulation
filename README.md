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

**Connections.** The driver holds **one persistent connection per instrument**,
shared by the poller and every command and reconnected automatically if it drops.
This matters: E4360 mainframes (like most Keysight LAN instruments) accept only a
few simultaneous connections — a raw-socket port often just one — so anything else
holding a connection to the same instrument (a telnet session on 5024/5025, another
VISA client, an earlier build of this app opening one connection per poll) can make
the unit read *unreachable* here while the other client still works. When a unit is
unreachable the UI shows the exact failure reason (Configuration → Simulator Units,
Device Identity, and the front panel's `NO COMMS` screen), e.g.
`Connection refused — instrument up but not accepting another connection?`. Close
the other session and the app recovers within a second or two on its own.

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
- **Transport** — `auto` (default): tries `vxi11` then `socket` and pins whichever
  answers. `vxi11`: VISA `TCPIP0::<ip>::INSTR`, the LAN interface the Programmer's
  Reference documents. `socket`: the same SCPI over a plain TCP port
  (`TCPIP0::<ip>::<port>::SOCKET`) — a fixed SCPI socket port is **not** documented in
  this guide, so only pin it if your instrument's LAN configuration page confirms it.
- **Port** — used by the socket transport only.
- **Channel** — 1 or 2.
- **MAC address** — a label for your inventory; not used for communication.

Platform-level soft limits (32 V / 6 A, `data.OPERATIONAL_LIMITS`) are enforced before a
command is sent; the instrument enforces its own module ratings on top.

### Channels

An E4360 mainframe holds up to two output modules, and **one unit here is one
channel**, so each is addressed, polled, controlled and audited independently.
Configuration → Simulator Units → **Discover channels** asks every configured
mainframe `SYST:CHAN?` and creates a unit for any channel not set up yet (named
`<unit>-CH<n>`). Measurements groups the channel chips by mainframe and plots all
of them by default. A mainframe is identified by its full address, not just its
IP — two units can share an IP and differ by port.

### Presets and saved states

Two different mechanisms, deliberately kept apart:

- **Presets** (Configuration → Presets) are stored by *this platform* — up to 10,
  named, each either a FIX pair (V, A) or a SAS curve (Isc, Imp, Vmp, Voc), with
  enable / insert / delete / apply. Applying one selects the mode and sends the
  values as ordinary SCPI, confirmed by readback and audited like any manual
  command. They are also recallable from the Virtual Front Panel
  (Menu → Recall preset) and the control screen.
- **Instrument states** are the E4360's own `*SAV 0|1` / `*RCL 0|1` — exactly two
  locations in the instrument's non-volatile memory, mainframe-wide (both
  channels), available from the Virtual Front Panel (Menu → Save/Recall state).
  The guide cautions that NVRAM has a finite write-cycle budget, so `*SAV` is
  only ever an explicit operator action, never automatic.

Values are validated identically wherever they are sent — manual control, preset
or profile — against the platform soft limits in `data.OPERATIONAL_LIMITS` plus
the SAS coupling rules (Vmp < Voc, Imp ≤ Isc). A preset that would violate them
is refused at storage time rather than failing later at the instrument.

### Operating modes and "Apply Solar Profile"

`CURR:MODE FIX|SAS,(@n)` selects how the channel behaves, and the two are genuinely
separate modes — the control screen shows them as two panels with the active one
highlighted. In **FIX** mode the output is a fixed rectangular V/I characteristic set
by `VOLT`/`CURR`. In **SAS** mode it follows an exponential solar-array I-V curve
defined by **four coupled parameters** — short-circuit current, the current and
voltage at the peak-power point, and open-circuit voltage — sent in one message so
the instrument validates the whole curve and rejects it atomically:

```
CURR:SAS:ISC 4.6,(@1);IMP 4.2,(@1);:VOLT:SAS:VMP 28,(@1);VOC 32,(@1)
```

Rejections you will see: `320` Vmp ≥ Voc, `321` Imp > Isc, `322` peak point too
small, `328` Voc above the module rating. In SAS mode a plain `VOLT`/`CURR` is
rejected with `315 Settings conflict error` — the UI warns about this and shows the
rejection verbatim. The curve currently on the instrument is read back every poll
(`CURR:SAS:ISC?` …) and shown next to the values you're editing.

### Deploying for the lab (one backend for everyone)

Run **one** backend + frontend on a host that can reach the instruments (your
workstation, or a small lab server) and have everyone open
`http://<that-host>:3301`. Do **not** run a backend per user against the same
instruments: each backend would hold its own session, and an E4360 accepts only
one raw-socket client — they'd fight, and everyone would see *unreachable*. Both
servers already bind to all interfaces (`-H 0.0.0.0` / `--host 0.0.0.0`) and the
UI talks to the API through the Next.js proxy on the same origin, so nothing else
needs opening besides ports 3301 (and 8000 if someone wants Swagger).

The fleet an empty database is seeded from lives in `backend/fleet.json` — the
lab's real mainframes (`10.1.20.126`, `10.1.20.215`, transport `auto`). Anyone
cloning the repo therefore sees the real instruments, not the emulators. Edit
units afterwards from Configuration → Simulator Units; `fleet.json` is only read
when `data.db` is empty. For a no-hardware demo:

```bash
SAS_FLEET_FILE=fleet.emulator.json .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**If the units show the wrong address.** `fleet.json` is read only when `data.db`
is *empty*, so an existing database keeps whatever its units were addressed at.
Configuration → Simulator Units shows which host the backend runs on, the URL LAN
users should open, and a warning when units still point at the local emulators;
**Apply fleet file** re-addresses the stored units to match `fleet.json` (adding
missing ones) while keeping measurements, history and alarms.

**Diagnosing one unit.** Its **Diagnose** button probes that address *from the
backend host* — TCP 5024 / the socket port / 111, then a real `*IDN?` over both
VXI-11 and the socket — and prints a verdict: which transport to use, or whether
a session is held, or whether nothing answers at all. (`backend/probe.py <ip>`
does the same from a shell.)

**Stuck sessions.** Configuration → Simulator Units has **⟲ Reset all connections**
(drops every session *this app* holds and re-polls at once) and, per unit,
**Reboot** — `SYSTem:REBoot`, the documented way to make the mainframe drop *every*
session including a telnet left open on another machine (output goes OFF, ~30 s).
`backend/probe.py <ip>` tells you from the backend host which paths answer.

### Bundled emulators (no hardware needed)

`backend/app/emulator.py` is a software E4360 mainframe: it parses the same bytes the
driver would send to a physical unit — channel lists, implied header paths in compound
messages, long/short mnemonics, `*OPC?`, the `SYST:ERR?` FIFO with the guide's error
codes — and answers in the same formats, with FIX/SAS physics against a resistive load
and OVP/OCP latching into `STAT:QUES:COND?`. Two instances start on `127.0.0.1:5025` /
`:5026` whenever any unit is addressed at loopback (or `SAS_EMULATORS=1`); the
`fleet.emulator.json` fleet points **SAS-01**/**SAS-02** at them over the socket
transport. The driver code path is identical to the one used for real hardware.

### Run it

```bash
# backend (http://localhost:8000)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # includes pyvisa + pyvisa-py
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend (http://<host>:3301) — proxies /api/* to the backend above
cd frontend
npm install
npm run dev
```

Then open http://localhost:3301.

An existing `backend/data.db` is upgraded in place on startup (missing columns are
added), so your configured units survive updates. Delete it only if you want a fresh
seed:

```bash
rm backend/data.db   # optional: fresh schema + seed on next start
```

## Scenario Builder

The builder is a real editor over a persisted graph, and the runner walks that graph
against the instrument.

**Editing.** Drag a block from the left palette onto the canvas to add it; drag a block
to move it; drag the `○` on a block's right edge onto another block to connect them;
click a connection to remove it. Selecting a block opens its settings on the right,
where every parameter is editable — change *Set Voltage* to 21.5 V and that is the value
`VOLT 21.5,(@1)` carries on the next run. Values are range-checked server-side against
the same soft limits the front panel uses, so an out-of-range entry is refused with the
reason rather than silently stored. A **Threshold Check** block has a second, red port
for its fail path. Positions, parameters and connections all persist.

**Solar profiles.** An *Apply Solar Profile* block takes the four coupled curve values
either typed into the block or from a **stored SAS preset**. A preset is read when the
block runs, so editing the preset changes every scenario pointing at it, and only
enabled SAS presets can be selected. Typed values are checked against the instrument's
own coupling rules (Vmp < Voc, Imp ≤ Isc) before they are stored.

**Validation.** The graph is checked continuously and separates what blocks a run from
what is merely worth knowing.

*Problems* (Run stays disabled): not exactly one Start, a step with no next step, a block
unreachable from Start, a missing fail path, a profile block with no usable curve, and —
because the operating mode is propagated along the edges — a **Set Voltage or Set Current
that would run while the channel is in SAS mode**, which the instrument refuses with 315
settings conflict.

*Warnings* (the run is allowed): energising the output in SAS mode with no profile
programmed on the way there, and a profile block on a path that never leaves FIX mode,
where the curve is accepted and then ignored.

**CSV export.** An *Export CSV* block writes the run so far to `backend/exports/<run>.csv`
— it captures the steps before it, so put it late in the scenario. Whether or not the
scenario has one, the command-history panel offers the finished run as a download, either
every step or measurements only. Rows carry the run, scenario, target, wall-clock time,
seconds elapsed, block, level, message, the exact SCPI sent, the instrument's reply, the
latency, and the measured V/I/P as numbers — so it charts in Excel without cleaning.
Only the steps that actually took a reading carry one.

**Running.** Each block is dispatched as real SCPI, confirmed by readback and written to
the audit log. While the run is live:

- a read-only strip at the top shows elapsed time against the estimate, names the block
  currently executing and counts the steps taken. Its bar is a timeline: a tick marks
  where each step actually ran (hover for the block and its offset), red for a step that
  errored. While the run is live the axis is the estimate and the fill stops at 99%, so a
  bar that has caught up never looks like a finished run — if the run passes its estimate
  the label says so and the clock keeps counting. On completion the axis becomes the real
  duration, the bar fills, and it turns green for a completed run or red for a failed or
  aborted one. Elapsed is measured on the server, so the readout is correct on a machine
  whose clock differs from the backend host's;
- each block is colour-coded — **green** ready, **yellow** running, **grey** finished,
  **red** errored, dimmed for a branch not taken;
- the panel at the bottom lists every command the run has sent, with the exact SCPI
  string, the instrument's reply and the round-trip latency.

A run that reaches a **Safe Shutdown** block (because a check failed) finishes as
`Failed` with the output de-energised; `Aborted` is reserved for an operator pressing
Abort.

### What is still simulated

- The 24 h of measurement history seeded on first start is synthetic (so charts aren't
  empty); everything from that moment on is real polled data.
- Scenario versioning is cosmetic — editing a scenario does not bump `v1.4` or keep the
  previous revision.

### Offline

Fonts (IBM Plex Sans/Mono) are self-hosted under `frontend/public/fonts/` and
loaded via local `@font-face` rules in `app/globals.css` — no `next/font/google`
and no Google Fonts `<link>`. The frontend dev server and the running app need
no internet access at all.
