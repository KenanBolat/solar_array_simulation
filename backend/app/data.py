"""Static reference data — node/command vocabularies and the demo scenario
graph. Fleet/rack/measurement/history/alarm data now lives in the database
(see orm.py + seed.py); nothing about *that* is hardcoded here anymore.
"""

FEATURED_UNIT = "SAS-01"

# SAS-mode I-V curves, applied with the four coupled parameters in one message
# (CURR:SAS:ISC / CURR:SAS:IMP / VOLT:SAS:VMP / VOLT:SAS:VOC — see scpi.py).
# Values are for an E4361A module (65 V / 8.7 A) and sit inside the platform's
# 32 V / 6 A soft limits. Pmp = Vmp x Imp.
SAS_PROFILES = {
    "BOL_GEO_28V": {"voc": 32.0, "isc": 4.6, "vmp": 28.0, "imp": 4.2,
                    "desc": "Beginning-of-life panel, geostationary orbit, 28 V bus · Pmp 117.6 W"},
    "EOL_LEO_24V": {"voc": 27.5, "isc": 4.1, "vmp": 24.0, "imp": 3.7,
                    "desc": "End-of-life (degraded) panel, low-earth orbit, 24 V bus · Pmp 88.8 W"},
    "ECLIPSE_EXIT_COLD": {"voc": 32.0, "isc": 4.7, "vmp": 30.0, "imp": 4.3,
                          "desc": "Cold panel just after eclipse exit — elevated voltage · Pmp 129 W"},
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
    "profile": {
        "name": "Apply Solar Profile",
        "target": f"{FEATURED_UNIT} (single unit)",
        "params": [
            ["Profile", "BOL_GEO_28V"],
            ["Meaning", "Beginning-of-Life, Geostationary orbit, 28 V bus"],
            ["Voc / Isc", "32.0 V / 4.6 A"],
            ["Vmp / Imp", "28.0 V / 4.2 A  (Pmp 117.6 W)"],
            ["SCPI", "CURR:MODE SAS,(@1) then CURR:SAS:ISC 4.6,(@1);IMP 4.2,(@1);:VOLT:SAS:VMP 28,(@1);VOC 32,(@1)"],
        ],
        "delay": "0 ms", "timeout": "2 000 ms", "retry": "0 retries",
        "fail": "Abort scenario",
        "comments": ("Puts the channel in SAS mode and programs the exponential I-V curve the array should present "
                      "(open-circuit voltage, short-circuit current, and the peak-power point). All four parameters go "
                      "in one message so the instrument validates the curve as a whole and rejects it atomically "
                      "(errors 320-322/328). Note: in SAS mode the operating point is set by the load, so a plain "
                      "'Set Voltage' step afterwards is rejected with 315 Settings conflict — the scenario runner still "
                      "walks these steps as a simulated sequence; live per-step dispatch is the next milestone."),
    },
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

FP_MENU = ["Output On/Off", "Set Voltage", "Set Current Limit", "Mode FIX / SAS", "Clear Protection", "I/O Configuration"]

OPERATIONAL_LIMITS = {
    "max_voltage_v": 32.0,
    "max_current_a": 6.0,
    "max_power_w": 180.0,
    "allowed_output_state": "ON / OFF",
    "warning_threshold_power_w": 160,
    "critical_threshold_power_w": 175,
    "safe_shutdown_rule": "Ramp → OFF on critical",
}
