"""Static seed data matching the Claude Design wireframe for the
Solar Array Simulator Control Platform. Values here are illustrative /
simulated — nothing here talks to real hardware.
"""

RAW_UNITS = [
    # name,     rack, slot, online, output, alarm
    ("SAS-01", "A", 1, True, True, "normal"),
    ("SAS-02", "A", 2, True, True, "normal"),
    ("SAS-03", "A", 3, True, False, "normal"),
    ("SAS-04", "A", 4, True, True, "normal"),
    ("SAS-05", "A", 5, False, False, "offline"),
    ("SAS-06", "A", 6, True, False, "normal"),
    ("SAS-08", "B", 1, True, True, "normal"),
    ("SAS-09", "B", 2, True, False, "normal"),
    ("SAS-07", "B", 3, True, True, "warning"),
    ("SAS-10", "B", 4, True, True, "normal"),
    ("SAS-11", "B", 5, True, False, "normal"),
    ("SAS-12", "B", 6, False, False, "offline"),
    ("SAS-13", "B", 7, True, True, "normal"),
    ("SAS-14", "C", 1, True, True, "normal"),
    ("SAS-15", "C", 2, True, False, "normal"),
    ("SAS-16", "C", 3, True, True, "normal"),
    ("SAS-17", "C", 4, True, False, "normal"),
    ("SAS-18", "C", 5, True, True, "normal"),
    ("SAS-19", "C", 6, False, False, "offline"),
    ("SAS-20", "C", 7, True, False, "normal"),
]

RACK_META = {
    "A": {"name": "RACK-A", "loc": "Lab 2 · Bay 1", "cap": 8},
    "B": {"name": "RACK-B", "loc": "Lab 2 · Bay 2", "cap": 8},
    "C": {"name": "RACK-C", "loc": "Lab 3 · Bay 1", "cap": 8},
}

FEATURED_UNIT = "SAS-07"
FEATURED_VOLTAGE = 28.0
FEATURED_CURRENT = 4.2
FEATURED_POWER = 117.6

ALARMS_SEED = [
    {"id": 0, "time": "14:32:09", "unit": "SAS-07", "code": "PWR_NEAR_LIMIT", "sev": "warning",
     "msg": "Output power approaching configured limit (158.2 W of 160 W)", "active": True},
    {"id": 1, "time": "13:58:44", "unit": "SAS-12", "code": "COMM_LOST", "sev": "warning",
     "msg": "Communication lost — no response after 3 polling intervals", "active": True},
    {"id": 2, "time": "12:10:02", "unit": "SAS-04", "code": "SETPOINT_OK", "sev": "info",
     "msg": "Voltage setpoint applied within tolerance", "active": False},
    {"id": 3, "time": "09:45:21", "unit": "SAS-19", "code": "MAINT_MODE", "sev": "info",
     "msg": "Scheduled maintenance — unit disabled by administrator", "active": False},
    {"id": 4, "time": "08:52:55", "unit": "SAS-12", "code": "CMD_FAILED", "sev": "critical",
     "msg": "read_measurements failed after 2 retries — safe shutdown dispatched", "active": False},
]

HISTORY_SEED = [
    {"t": "14:33:01", "user": "a.ng", "dev": "SAS-07", "tpl": "output_on", "st": "OK", "lat": "38 ms", "rb": True, "cid": "CMD-9F2A"},
    {"t": "14:32:40", "user": "a.ng", "dev": "SAS-07", "tpl": "set_voltage", "st": "OK", "lat": "41 ms", "rb": True, "cid": "CMD-9F29"},
    {"t": "14:31:58", "user": "system", "dev": "SAS-07", "tpl": "read_measurements", "st": "OK", "lat": "22 ms", "rb": False, "cid": "CMD-9F21"},
    {"t": "14:30:12", "user": "r.diaz", "dev": "SAS-10", "tpl": "set_current_limit", "st": "OK", "lat": "44 ms", "rb": True, "cid": "CMD-9F0C"},
    {"t": "14:28:03", "user": "r.diaz", "dev": "SAS-11", "tpl": "output_off", "st": "WARN", "lat": "2410 ms", "rb": False, "cid": "CMD-9EF7"},
    {"t": "14:26:55", "user": "system", "dev": "SAS-12", "tpl": "read_measurements", "st": "ERR", "lat": "5000 ms", "rb": False, "cid": "CMD-9EE1"},
    {"t": "14:24:30", "user": "a.ng", "dev": "SAS-14", "tpl": "apply_profile", "st": "OK", "lat": "66 ms", "rb": True, "cid": "CMD-9ED3"},
    {"t": "14:22:11", "user": "k.imai", "dev": "SAS-16", "tpl": "identify", "st": "OK", "lat": "18 ms", "rb": True, "cid": "CMD-9EC0"},
    {"t": "14:19:47", "user": "a.ng", "dev": "SAS-01", "tpl": "safe_shutdown", "st": "OK", "lat": "120 ms", "rb": True, "cid": "CMD-9EA4"},
    {"t": "14:17:02", "user": "r.diaz", "dev": "SAS-18", "tpl": "set_voltage", "st": "OK", "lat": "39 ms", "rb": True, "cid": "CMD-9E91"},
]

RUNS_SEED = [
    {"id": "RUN-8842", "scenario": "Eclipse Cycle — Panel A", "version": "v1.4", "status": "Running", "dry": False,
     "prog": 62, "targets": ["SAS-07"], "by": "a.ng", "started": "14:20:03", "finished": "—", "dur": "13m 04s"},
    {"id": "RUN-8841", "scenario": "BOL Power Sweep", "version": "v2.1", "status": "Running", "dry": False,
     "prog": 18, "targets": ["SAS-10", "SAS-11"], "by": "r.diaz", "started": "14:05:41", "finished": "—", "dur": "27m 26s"},
    {"id": "RUN-8838", "scenario": "Thermal Vac Profile", "version": "v1.0", "status": "Completed", "dry": False,
     "prog": 100, "targets": ["SAS-14", "SAS-16", "SAS-18"], "by": "a.ng", "started": "11:40:12", "finished": "12:58:33", "dur": "1h 18m"},
    {"id": "RUN-8836", "scenario": "Eclipse Cycle — Panel A", "version": "v1.3", "status": "Completed", "dry": True,
     "prog": 100, "targets": ["SAS-07"], "by": "a.ng", "started": "10:22:00", "finished": "10:24:10", "dur": "2m 10s"},
    {"id": "RUN-8831", "scenario": "Safe Shutdown Drill", "version": "v1.1", "status": "Aborted", "dry": False,
     "prog": 34, "targets": ["SAS-01", "SAS-02"], "by": "system", "started": "09:12:44", "finished": "09:14:02", "dur": "1m 18s"},
    {"id": "RUN-8829", "scenario": "Isc Calibration", "version": "v3.0", "status": "Failed", "dry": False,
     "prog": 71, "targets": ["SAS-12"], "by": "r.diaz", "started": "08:41:19", "finished": "08:52:55", "dur": "11m 36s"},
]

RUN_EVENTS_SEED = {
    "RUN-8842": [
        {"t": "14:20:03", "node": "start", "lvl": "info", "m": "Run accepted — scenario v1.4 approved · 1 target · correlation RUN-8842"},
        {"t": "14:20:03", "node": "profile", "lvl": "ok", "m": "apply_profile BOL_GEO_28V → ACK"},
        {"t": "14:20:05", "node": "setv", "lvl": "ok", "m": "set_voltage 28.0 V → ACK · readback verified"},
        {"t": "14:20:06", "node": "enable", "lvl": "ok", "m": "output_on → completed"},
        {"t": "14:20:16", "node": "wait", "lvl": "info", "m": "wait 10 000 ms elapsed"},
        {"t": "14:20:17", "node": "read", "lvl": "ok", "m": "read_measurements → 28.002 V · 4.198 A · 117.55 W"},
        {"t": "14:20:17", "node": "thresh", "lvl": "ok", "m": "threshold_check power_w >= 100 → true"},
        {"t": "14:20:18", "node": "record", "lvl": "ok", "m": "record_measurement → run_log row 412"},
        {"t": "14:25:41", "node": "wait", "lvl": "warn", "m": "iteration 3 — comms latency 812 ms above nominal"},
        {"t": "14:33:01", "node": "read", "lvl": "info", "m": "iteration 7 of 12 in progress"},
    ],
    "RUN-8829": [
        {"t": "08:41:19", "node": "start", "lvl": "info", "m": "Run accepted — scenario v3.0 · 1 target"},
        {"t": "08:41:20", "node": "enable", "lvl": "ok", "m": "output_on → completed"},
        {"t": "08:49:02", "node": "read", "lvl": "warn", "m": "read_measurements retry 1 of 2 — response timeout"},
        {"t": "08:52:54", "node": "read", "lvl": "err", "m": "read_measurements failed — device unreachable after 2 retries"},
        {"t": "08:52:55", "node": "shutdown", "lvl": "err", "m": "failure action → safe_shutdown dispatched · output disabled"},
    ],
}

SCENARIO = {
    "id": "eclipse-cycle-panel-a",
    "name": "Eclipse Cycle — Panel A",
    "version": "v1.4",
    "state": "DRAFT",
}

NODE_DEFS = [
    {"id": "start", "type": "START", "label": "Start", "x": 50, "y": 50, "kind": "terminal"},
    {"id": "profile", "type": "PROFILE", "label": "Apply Solar Profile", "sub": "BOL_GEO_28V", "x": 255, "y": 50, "kind": "action"},
    {"id": "setv", "type": "SET", "label": "Set Voltage", "sub": "28.0 V", "x": 460, "y": 50, "kind": "action"},
    {"id": "enable", "type": "OUTPUT", "label": "Enable Output", "sub": "OUTP:STAT ON", "x": 665, "y": 50, "kind": "action"},
    {"id": "wait", "type": "WAIT", "label": "Wait / Delay", "sub": "10 000 ms", "x": 870, "y": 50, "kind": "flow"},
    {"id": "read", "type": "MEASURE", "label": "Read V · I · P", "sub": "MEAS:ALL?", "x": 870, "y": 215, "kind": "measure"},
    {"id": "thresh", "type": "CHECK", "label": "Threshold Check", "sub": "Power > 100 W", "x": 625, "y": 215, "kind": "logic"},
    {"id": "record", "type": "RECORD", "label": "Record Measurement", "sub": "run_log", "x": 380, "y": 215, "kind": "measure"},
    {"id": "disable", "type": "OUTPUT", "label": "Disable Output", "sub": "OUTP:STAT OFF", "x": 135, "y": 215, "kind": "action"},
    {"id": "end", "type": "END", "label": "End", "x": 135, "y": 380, "kind": "terminal"},
    {"id": "shutdown", "type": "SAFETY", "label": "Safe Shutdown", "sub": "fail path", "x": 625, "y": 380, "kind": "danger"},
]

# (from, to, kind[R|B], fail?)
EDGE_DEFS = [
    ("start", "profile", "R", False),
    ("profile", "setv", "R", False),
    ("setv", "enable", "R", False),
    ("enable", "wait", "R", False),
    ("wait", "read", "B", False),
    ("read", "thresh", "R", False),
    ("thresh", "record", "R", False),
    ("record", "disable", "R", False),
    ("disable", "end", "B", False),
    ("thresh", "shutdown", "B", True),
]

NODE_PROPS_OVERRIDE = {
    "thresh": {
        "name": "Threshold Check",
        "target": "SAS-07 (single unit)",
        "params": [
            ["Source measurement", "Power (W)"],
            ["Operator", "greater than (>)"],
            ["Threshold", "100.0 W"],
            ["On true → next", "Record Measurement"],
            ["On false → next", "Safe Shutdown"],
        ],
        "delay": "0 ms", "timeout": "2 000 ms", "retry": "1 retry · 500 ms backoff",
        "fail": "Branch to Safe Shutdown",
        "comments": "Guards against under-power condition before logging a pass result.",
    }
}

NODE_PALETTE = [
    "Start", "End", "Set Output State", "Set Voltage", "Set Current Limit",
    "Apply Simulator Profile", "Wait / Delay", "Read Measurement", "Record Measurement",
    "Threshold Check", "Condition / Branch", "Repeat", "Send Validated Command",
    "Safe Shutdown", "Notification", "Comment",
]

TERM_CMDS = [
    {"name": "open", "aliases": ["open", "on", "enable", "enable output", "output on"],
     "summary": "Enable the output — energises the array", "effect": "output ON — array energised",
     "hazardous": True, "act": "on"},
    {"name": "close", "aliases": ["close", "off", "disable", "disable output", "output off"],
     "summary": "Disable the output — de-energises the array", "effect": "output OFF — array de-energised",
     "hazardous": False, "act": "off"},
    {"name": "read", "aliases": ["read current measurements", "read measurements", "read", "measure", "meas"],
     "summary": "Read voltage, current and power now", "hazardous": False, "act": "read"},
    {"name": "status", "aliases": ["status", "state"],
     "summary": "Show cached device status without querying", "hazardous": False, "act": "status"},
    {"name": "identify", "aliases": ["identify", "id", "whoami"],
     "summary": "Ask the instrument to identify itself", "hazardous": False, "act": "idn"},
    {"name": "set voltage", "aliases": ["set voltage", "voltage", "volt", "v"],
     "summary": "Set the programmed output voltage", "usage": "set voltage 28.0",
     "hazardous": True, "act": "setv", "unit": "V", "max": 32},
    {"name": "set current", "aliases": ["set current limit", "set current", "current", "curr", "i"],
     "summary": "Set the programmed current limit", "usage": "set current 4.5",
     "hazardous": True, "act": "seti", "unit": "A", "max": 6},
    {"name": "shutdown", "aliases": ["shutdown", "safe shutdown", "stop"],
     "summary": "Disable output and bring the unit to a safe state",
     "effect": "safe shutdown — output disabled, unit to standby", "hazardous": True, "act": "shutdown"},
    {"name": "help", "aliases": ["help", "?", "commands"],
     "summary": "List every command this terminal accepts", "hazardous": False, "act": "help"},
    {"name": "clear", "aliases": ["clear", "cls"],
     "summary": "Clear the transcript", "hazardous": False, "act": "clear"},
]

FP_MENU = ["Output On/Off", "Set Voltage", "Set Current Limit", "SAS Curve Mode", "Protection Limits", "I/O Configuration"]

RACK_B_ASSIGN_SEED = {"B1": "SAS-08", "B2": "SAS-09", "B3": "SAS-07", "B4": "SAS-10", "B5": "SAS-11", "B6": "", "B7": "SAS-13"}
RACK_B_PALETTE_SEED = ["SAS-12", "SAS-24", "SAS-25"]

OPERATIONAL_LIMITS = {
    "max_voltage_v": 32.0,
    "max_current_a": 6.0,
    "max_power_w": 180.0,
    "allowed_output_state": "ON / OFF",
    "warning_threshold_power_w": 160,
    "critical_threshold_power_w": 175,
    "safe_shutdown_rule": "Ramp → OFF on critical",
}
