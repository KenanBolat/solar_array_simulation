"""Static reference data — node/command vocabularies and the demo scenario
graph. Fleet/rack/measurement/history/alarm data now lives in the database
(see orm.py + seed.py); nothing about *that* is hardcoded here anymore.
"""

FEATURED_UNIT = "SAS-01"
FEATURED_VOLTAGE = 28.0
FEATURED_CURRENT = 4.2
FEATURED_POWER = 117.6

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
        "target": f"{FEATURED_UNIT} (single unit)",
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

OPERATIONAL_LIMITS = {
    "max_voltage_v": 32.0,
    "max_current_a": 6.0,
    "max_power_w": 180.0,
    "allowed_output_state": "ON / OFF",
    "warning_threshold_power_w": 160,
    "critical_threshold_power_w": 175,
    "safe_shutdown_rule": "Ramp → OFF on critical",
}
