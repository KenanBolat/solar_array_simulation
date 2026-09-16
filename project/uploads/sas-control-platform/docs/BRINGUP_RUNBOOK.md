# Bring-up runbook — two units, LAN raw socket, bench only

Concrete sequence for taking this platform from simulation to two real
E4360 channels. Written for the configuration you described: **LAN (SOCKET)
transport, shared lab network, single operator, outputs disconnected from any
load for first bring-up.**

Work top to bottom. Every phase has an exit condition — do not start the next
phase until the current one passes. Phases 0–2 involve no risk to hardware.

> **The one rule:** never fill in a SCPI string you have not read in the
> programming manual for *your* firmware revision. A wrong command string sent
> to an energised supply is not a bug, it is an incident. Unverified operations
> are refused by the driver — that block exists to protect you, so lift it one
> line at a time.

---

## Phase 0 — Before touching the software

**Network and addressing**
- [ ] Each unit has a known, static IP (or a reserved DHCP lease).
- [ ] Raw-socket SCPI port confirmed in the manual — **5025** unless stated otherwise.
- [ ] `ping` reaches each instrument from the machine that will run the API.
- [ ] Any firewall between API host and instruments allows outbound TCP on that port.

**Instrument-side protection — do this first, not last**
- [ ] Hardware **OVP** set on each channel.
- [ ] Hardware **OCP** / current limit set on each channel.
- [ ] Interlock wiring confirmed, and you know how the channel behaves when it opens.
- [ ] E-stop confirmed, and you have verified what it actually cuts.
- [ ] Per-channel voltage/current ratings written down — these become your soft limits.

The platform's soft limits are advisory. The instrument's own protection is the
only thing that acts without software in the loop.

**Firmware**
- [ ] Firmware revision recorded per mainframe. The capability map is
      firmware-versioned; a different revision may use different syntax.

### ⚠ Shared lab network — read this

You said the API host and instruments will share the lab network. Two defaults
in `app/config.py` are unsafe in that setting:

```python
jwt_secret: str = "change-me-in-production"
dev_auth_enabled: bool = True     # trusts an X-Dev-User header
```

With `dev_auth_enabled=true`, **anyone who can reach the API can impersonate any
user and energise your hardware** by sending a header. On an isolated bench
network that is an acceptable convenience. On a shared network it is not.

Minimum before hardware is enabled:
- [ ] Change `SAS_JWT_SECRET` to a real secret.
- [ ] Either bind the API to `127.0.0.1` (single-user, browser on the same host —
      which fits your setup), **or** set `SAS_DEV_AUTH_ENABLED=false` and log in properly.
- [ ] Restrict `SAS_CORS_ORIGINS` to the actual frontend origin.

**Exit condition:** you can ping both instruments, protection is set on both,
and the API is not reachable unauthenticated from the wider network.

---

## Phase 1 — Prove the link outside the application

Confirm VISA before any application code is involved. This separates network
problems from driver problems, which are otherwise very easy to confuse.

```python
import pyvisa
rm = pyvisa.ResourceManager()
inst = rm.open_resource("TCPIP0::<IP>::5025::SOCKET")
inst.read_termination  = "\n"     # REQUIRED for SOCKET
inst.write_termination = "\n"     # REQUIRED for SOCKET
inst.timeout = 5000
print(inst.query("*IDN?"))
inst.close()
```

**If `*IDN?` hangs**, it is almost always one of three things, in this order of
likelihood: missing termination settings (raw sockets have no built-in message
termination), wrong port, or a firewall. It is rarely the instrument.

- [ ] `*IDN?` returns a sane identity string from **unit 1**.
- [ ] `*IDN?` returns a sane identity string from **unit 2**.
- [ ] Record both identity strings and both resource strings.

**Exit condition:** both units identify themselves from the API host.

---

## Phase 2 — Describe your bench to the platform

Still zero hardware risk: the units are created on the **mock** driver.

1. Edit `app/seed_hardware.py`, the `EDIT THIS BLOCK` section:
   - `MAINFRAME["model"]` — from the chassis label
   - each unit's `module_model`, `slot`, `channel`, `ip`
   - each unit's `max_voltage_v` / `max_current_a` — the **per-channel ratings**
     from Phase 0
2. Seed it:

```bash
cd backend
python -m app.seed_hardware --reset      # replaces the 20-unit demo topology
```

The script refuses to run while any `FILL_ME` placeholder remains.

3. Start the stack and open the UI. You should see one rack, one mainframe and
   two units, with your real resource strings shown on each device page.

- [ ] Both units appear with correct slot/channel/resource.
- [ ] Soft limits on each unit match its real rating.
- [ ] Telemetry is flowing (from the mock driver — expected).

**Exit condition:** the platform's model of your bench is correct. Fix it here,
where mistakes cost nothing.

---

## Phase 3 — Fill in the SCPI table

Open `app/drivers/e4360.py` and work through `_SCPI_MAP`. Each entry carries a
`note` naming what to look up.

Fill in **this order** — least consequential first:

| Order | Operations | Why first |
|---|---|---|
| 1 | `read_voltage`, `read_current`, `read_power` | Read-only. Cannot change output state. |
| 2 | `select_channel` | Addressing. Get this wrong and you command the wrong channel. |
| 3 | `set_voltage`, `set_current_limit` + readbacks | Writes, but harmless with output off. |
| 4 | `output_on`, `output_off` + readback | First operation that can energise. |
| 5 | `sas_isc/imp/voc/vmp`, `sas_mode_on` | Curve definition. |

For each one:
- Paste the exact string; use `{ch}` for the channel selector and `{value}` for the parameter.
- **Pair every write with a `readback` query.** The platform verifies setpoints
  after every change; without a readback it reports `readback_verified=False`
  and you are flying blind.
- Set `verified=True` only after you have read it in the manual.

Two things that bite people here:
- **Channel addressing.** Confirm whether channels are selected by a separate
  command or a suffix on every command. If it is a suffix, leave
  `select_channel` as `None` and put `{ch}` in each string instead.
- **SAS parameter order.** A transposed `Isc`/`Imp` produces a plausible-looking
  but wrong curve, and nothing will flag it. Confirm the order explicitly.

- [ ] Every string you set to `verified=True` was read in the manual.
- [ ] Every `write` has a paired `readback`.

---

## Phase 4 — Commission unit 1, output disconnected

> **Physically disconnect the output terminals from any panel-under-test or
> load before this phase.** You confirmed bench-only; this is where it matters.

```bash
cd backend
python scripts/commission.py --resource "TCPIP0::<IP-1>::5025::SOCKET" --channel 1
```

Read-only walk: prints the verification table, connects, identifies, reads the
error queue, reads measurements, then writes low setpoints (5 V / 0.5 A) and
verifies readback. It stops at the first failure. `SKIP` means an operation is
still unverified — expected until Phase 3 is complete for it.

When setpoints pass, include the output test:

```bash
python scripts/commission.py --resource "TCPIP0::<IP-1>::5025::SOCKET" \
    --channel 1 --allow-output
```

This requires you to type `DISCONNECTED` to proceed, enables the output, takes a
measurement, and **always disables it again** — including if the measurement
raises.

- [ ] Steps 1–6 pass on unit 1.
- [ ] Output enable/disable passes, with readback confirming the state.
- [ ] Safe-shutdown path passes.
- [ ] Repeat all of the above for **unit 2**.

**Exit condition:** both units pass the full walk with outputs disconnected.

---

## Phase 5 — Enable hardware in the platform

```bash
cd backend
python -m app.seed_hardware --reset --real     # bind units to the e4360 driver
```

Then set, in your environment:

```
SAS_HARDWARE_ENABLED=true
SAS_JWT_SECRET=<a real secret>
SAS_TELEMETRY_INTERVAL_SECONDS=2.0     # tune: real LAN polling is slower than mock
```

Bump `CAPABILITY_MAP_VERSION` in `app/drivers/templates.py` so the change is
traceable in the audit log.

Telemetry interval deserves a thought: the mock polls at 1 s. Two units over LAN
with several queries per poll may not keep up, and a saturated command queue
delays the commands you actually care about. Start at 2 s and lower it only if
measurements keep pace.

- [ ] Device pages show **SCPI verified** on the templates you completed.
- [ ] Templates you did not complete still show unverified and are refused.
- [ ] Live telemetry matches the instrument's own front-panel display.

---

## Phase 6 — First controlled operation

Outputs still disconnected. Drive one unit from each surface in turn, and
confirm each appears in **Command History** with an actor and correlation id:

- [ ] `read` from the **Command Terminal**
- [ ] Set a low voltage from the **Virtual Front Panel**, confirm readback
- [ ] Enable then disable output from **Safe Controls**, via the confirm dialog
- [ ] Run **Safe Shutdown** and confirm the output actually drops

Then, and only then, connect a load and repeat at a real operating point.

- [ ] Every command appears in the audit log with correct actor and correlation id.
- [ ] Alarm behaviour verified: pull a network cable and confirm the unit goes
      offline and raises an alarm rather than silently reporting stale values.

---

## Phase 7 — Scenarios

Only after Phase 6.

- [ ] Build a trivial scenario: Start → Read → End. Dry-run it.
- [ ] Dry-run a scenario containing `output_on`, and confirm nothing energises.
- [ ] Run a real scenario on one unit, outputs disconnected.
- [ ] Verify Abort mid-run leaves the output **off**.

That last check is the one worth doing carefully. An abort that leaves an
output energised is the worst failure mode this system has.

---

## Rollback

If anything behaves unexpectedly:

1. `SAS_HARDWARE_ENABLED=false` — every device reverts to the mock driver immediately.
2. Physically disable outputs at the instrument.
3. The audit log retains every command sent; use the correlation id from
   Command History to trace what happened.

---

## Deliberately not automated

Judgement calls that stay manual, by design:

- Confirming SCPI strings against the manual.
- Setting hardware OVP/OCP.
- Deciding when the load may be connected.
- Commissioning sign-off per unit.
