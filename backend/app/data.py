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

# ---------------------------------------------------------------------------
# Node type registry. Each entry declares what the block does, how it looks on
# the canvas, and the parameters an operator can edit — the UI renders its
# editor straight from `params`, and the runner reads the same keys when it
# dispatches. Adding a block type here makes it appear in the palette, the
# editor and the runner at once.
# ---------------------------------------------------------------------------
# How large a block is drawn on the builder canvas. The backend needs it only to
# place a dropped block clear of the ones already there; the frontend owns the
# rendering and keeps the same numbers.
BLOCK_W, BLOCK_H = 178, 62

# Where an Apply Solar Profile block gets its four curve values. A param marked
# with `only` is shown and validated for just that source.
CURVE_MANUAL = "Manual values"
CURVE_PRESET = "Stored preset"

# What an Export CSV block writes: every step, or only the steps that produced a
# reading (the shape you want for a chart in Excel).
EXPORT_ALL = "Every step"
EXPORT_MEASURED = "Measurements only"

NODE_TYPES = {
    "start": {"label": "Start", "kind": "terminal", "badge": "START", "params": [],
              "help": "Where the run begins. Exactly one per scenario."},
    "end": {"label": "End", "kind": "terminal", "badge": "END", "params": [],
            "help": "Marks a successful finish."},
    "mode": {"label": "Set Mode", "kind": "action", "badge": "MODE",
             "params": [{"key": "mode", "label": "Operating mode", "type": "select",
                          "options": ["FIX", "SAS"], "default": "FIX"}],
             "help": "CURR:MODE — FIX drives a fixed V/I point, SAS follows the programmed array curve."},
    "setv": {"label": "Set Voltage", "kind": "action", "badge": "SET",
             "params": [{"key": "volts", "label": "Voltage", "type": "number", "unit": "V",
                          "default": 28.0, "min": 0, "max": 32, "step": 0.1}],
             "help": "VOLT — FIX mode only; the instrument answers 315 if the channel is in SAS mode."},
    "seti": {"label": "Set Current Limit", "kind": "action", "badge": "SET",
             "params": [{"key": "amps", "label": "Current limit", "type": "number", "unit": "A",
                          "default": 5.0, "min": 0, "max": 6, "step": 0.1}],
             "help": "CURR — FIX mode only."},
    "sas": {"label": "Apply Solar Profile", "kind": "action", "badge": "PROFILE",
            "params": [{"key": "source", "label": "Curve from", "type": "select",
                         "options": [CURVE_MANUAL, CURVE_PRESET], "default": CURVE_MANUAL},
                        {"key": "preset", "label": "Stored preset", "type": "preset", "default": 0,
                         "only": CURVE_PRESET},
                        {"key": "isc", "label": "Isc — short circuit", "type": "number", "unit": "A", "default": 4.6, "min": 0, "max": 6, "step": 0.1, "only": CURVE_MANUAL},
                        {"key": "imp", "label": "Imp — at peak power", "type": "number", "unit": "A", "default": 4.2, "min": 0, "max": 6, "step": 0.1, "only": CURVE_MANUAL},
                        {"key": "vmp", "label": "Vmp — at peak power", "type": "number", "unit": "V", "default": 28.0, "min": 0, "max": 32, "step": 0.1, "only": CURVE_MANUAL},
                        {"key": "voc", "label": "Voc — open circuit", "type": "number", "unit": "V", "default": 32.0, "min": 0, "max": 32, "step": 0.1, "only": CURVE_MANUAL}],
            "help": "The four coupled SAS curve parameters, sent in one message so the instrument validates the "
                     "curve as a whole. Either type them here or point the block at a stored SAS preset, in which "
                     "case the preset's values are read at run time — edit the preset and every scenario using it "
                     "follows."},
    "output": {"label": "Set Output", "kind": "action", "badge": "OUTPUT",
               "params": [{"key": "on", "label": "Output state", "type": "select",
                            "options": ["ON", "OFF"], "default": "ON"}],
               "help": "OUTP — energises or de-energises the channel, confirmed by readback."},
    "wait": {"label": "Wait / Delay", "kind": "flow", "badge": "WAIT",
             "params": [{"key": "ms", "label": "Duration", "type": "number", "unit": "ms",
                          "default": 5000, "min": 0, "max": 600000, "step": 500}],
             "help": "Holds the sequence so the output can settle. Nothing is sent to the instrument."},
    "measure": {"label": "Read V · I · P", "kind": "measure", "badge": "MEASURE", "params": [],
                "help": "MEAS:VOLT? / FETC:CURR? — takes a fresh reading and keeps it for the steps that follow."},
    "threshold": {"label": "Threshold Check", "kind": "logic", "badge": "CHECK",
                  "params": [{"key": "source", "label": "Source", "type": "select",
                               "options": ["power", "voltage", "current"], "default": "power"},
                              {"key": "op", "label": "Operator", "type": "select",
                               "options": [">", ">=", "<", "<=" ], "default": ">"},
                              {"key": "value", "label": "Threshold", "type": "number", "unit": "", "default": 100.0, "step": 1}],
                  "help": "Compares the last reading. Pass follows the solid edge; fail follows the dashed one."},
    "record": {"label": "Record Measurement", "kind": "measure", "badge": "RECORD", "params": [],
               "help": "Writes the last reading into the run log."},
    "export": {"label": "Export CSV", "kind": "measure", "badge": "EXPORT",
               "params": [{"key": "what", "label": "Rows to write", "type": "select",
                            "options": [EXPORT_ALL, EXPORT_MEASURED], "default": EXPORT_ALL}],
               "help": "Writes the run so far to a CSV file on the server — one row per step, with the exact "
                        "SCPI sent, the instrument's reply, the latency and the measured V/I/P. It captures "
                        "the steps before it, so put it late in the scenario. For the finished run in full, "
                        "use the download buttons under the command history."},
    "shutdown": {"label": "Safe Shutdown", "kind": "danger", "badge": "SAFETY", "params": [],
                 "help": "OUTP OFF — de-energises the channel and ends the run."},
}

# The default scenario seeded into a fresh database: a FIX-mode cycle that runs
# cleanly end to end against a real instrument.
DEFAULT_SCENARIO_ID = "eclipse-cycle-panel-a"
DEFAULT_NODES = [
    ("n_start", "start", 40, 60, {}),
    ("n_mode", "mode", 220, 60, {"mode": "FIX"}),
    ("n_setv", "setv", 420, 60, {"volts": 28.0}),
    ("n_seti", "seti", 620, 60, {"amps": 5.0}),
    ("n_on", "output", 820, 60, {"on": "ON"}),
    ("n_wait", "wait", 820, 200, {"ms": 3000}),
    ("n_read", "measure", 620, 200, {}),
    ("n_check", "threshold", 420, 200, {"source": "power", "op": ">", "value": 100.0}),
    ("n_record", "record", 220, 200, {}),
    ("n_off", "output", 40, 200, {"on": "OFF"}),
    ("n_end", "end", 40, 340, {}),
    ("n_safe", "shutdown", 420, 340, {}),
]
DEFAULT_EDGES = [
    ("n_start", "n_mode", False), ("n_mode", "n_setv", False), ("n_setv", "n_seti", False),
    ("n_seti", "n_on", False), ("n_on", "n_wait", False), ("n_wait", "n_read", False),
    ("n_read", "n_check", False), ("n_check", "n_record", False), ("n_record", "n_off", False),
    ("n_off", "n_end", False), ("n_check", "n_safe", True),
]

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
