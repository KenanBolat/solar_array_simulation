# Hardware Integration — what is required before connecting real instruments

The platform ships in **simulation mode**. Before a single real command is sent
to a Keysight E4360A, the following must be gathered and verified. Until then,
`SAS_HARDWARE_ENABLED` stays `false` and every device uses the mock driver.

> The real driver (`app/drivers/e4360.py`) is intentionally inert: only `*IDN?`
> is treated as verified. Every other command string is a placeholder marked
> `# TODO: verify against manual` and the driver refuses to send unverified
> commands. This file is the checklist to lift that block safely.

## 1. The official programming reference
- The **Keysight E4360 Modular Solar Array Simulator — SCPI/Programming Guide**
  for your firmware revision. Every command string below must be confirmed
  against it. Do not rely on the placeholders in this repository.

## 2. Verified SCPI command strings (per template)
For each command template in `app/drivers/templates.py`, provide the exact,
manual-confirmed SCPI (including channel syntax) and expected response/units:

| Template | Placeholder intent | Need from manual |
|---|---|---|
| `identify` | `*IDN?` | ✅ already standard — confirm response format. |
| `read_measurements` | read V / I | Exact `MEAS:VOLT?` / `MEAS:CURR?` (or combined) syntax and per-channel addressing. |
| `set_voltage` | set output voltage | `SOUR:VOLT` (or SAS-table equivalent) syntax, range, units. |
| `set_current_limit` | set current limit | `SOUR:CURR` syntax, range, units. |
| `configure_sas_table` | set Isc/Imp/Voc/Vmp | The SAS-table command group and parameter order/units. |
| `output_on` / `output_off` | enable/disable output | `OUTP ON|OFF` per-channel syntax; settling/confirmation behaviour. |
| `apply_profile` | apply a saved operating point | Composition of the above; any required sequencing. |
| `safe_shutdown` | bring to safe state | The manufacturer-recommended safe-state sequence. |

Also confirm:
- **Channel/slot addressing** — how a logical unit maps to mainframe + slot +
  output, and the exact SCPI channel selector syntax.
- **Readback queries** used to verify each set command (the platform performs
  readback verification after every state change).
- **Error/status model** — `SYST:ERR?`, status byte / operation registers, and
  how faults surface so the driver can map them to alarms.

## 3. Connection (VISA) details — per unit
- Transport: **LAN (TCPIP/SOCKET or VXI-11)**, **GPIB**, or **USB**.
- The exact **VISA resource string** for each unit, e.g.
  `TCPIP0::192.168.10.21::inst0::INSTR` or `GPIB0::5::INSTR`. The seed data uses
  `TCPIP0::192.168.10.X::...` **placeholders** that must be replaced.
- IP addressing / subnet / VLAN for the instrument network, and firewall rules
  from the API host to each instrument.
- VISA backend to use on the API host (Keysight IO Libraries or pyvisa-py) and
  confirmation it is installed in the deployment image.

## 4. Per-unit electrical and safety data
- **Hardware** over-voltage and over-current protection set points configured on
  each instrument (the app's soft limits are advisory only).
- Per-channel maximum voltage/current/power ratings, to set sane soft limits.
- Confirmation of **interlock wiring** and the behaviour of the output-enable
  interlock; the production output-enable path must check it.
- **E-stop** wiring and the expected instrument response to it.
- Firmware revision per mainframe (the capability map is firmware-versioned).

## 5. Operational confirmations
- Which channels are physically connected to which solar-panel-under-test or
  load, so logical unit names map correctly.
- Commissioning sign-off: a documented dry run on one unit with output
  **disconnected from the load** before fleet enablement.
- The intended value of `SAS_TELEMETRY_INTERVAL_SECONDS` given real instrument
  query latency (mock uses 1 s; real LAN polling may need tuning).

## 6. Enabling hardware (only after the above)
1. Fill verified SCPI strings into `app/drivers/templates.py` and flip each
   template's `verified` flag; implement the corresponding methods in
   `app/drivers/e4360.py`.
2. Replace the placeholder `visa_resource` values for the real units.
3. Set the connection profile `driver_kind` to the real driver for those units.
4. Set `SAS_HARDWARE_ENABLED=true` and bump the capability map version.
5. Commission one unit with the load disconnected; verify readback on every
   template before enabling the rest.
