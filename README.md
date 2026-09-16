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

- `backend/` — FastAPI service. In-memory mock state (20 units / 3 racks, alarms,
  command-audit log, scenario runs, scenario graph). No real hardware/SCPI driver —
  this is a simulation only, by design (see the handoff conversation in `chats/`).
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

# frontend (http://localhost:3000) — proxies /api/* to the backend above
cd frontend
npm install
npm run dev
```

Then open http://localhost:3000.
