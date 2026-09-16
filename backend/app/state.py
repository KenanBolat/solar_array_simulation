import asyncio
import time
from datetime import datetime, timezone
from itertools import count

from . import data
from .driver import compute_live_values, gen_series, RANGE_N, RANGE_SEED

_corr_seq = count(0x9F30, 1)


def now_hhmmss():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def next_corr_id():
    return "CMD-" + format(next(_corr_seq), "X")


class Unit:
    def __init__(self, name, rack, slot, online, output, alarm):
        self.name = name
        self.rack = rack
        self.slot = slot
        self.online = online
        self.output = output
        self.alarm = alarm  # "normal" | "warning" | "offline"
        self.voltage_setpoint = data.FEATURED_VOLTAGE if name == data.FEATURED_UNIT else 28.0
        self.current_limit = 5.0
        self.featured = name == data.FEATURED_UNIT

    @property
    def status_text(self):
        if not self.online:
            return "OFFLINE"
        if self.alarm == "warning":
            return "WARNING"
        if self.output:
            return "ACTIVE"
        return "ONLINE"

    @property
    def status_color(self):
        return {"OFFLINE": "faint", "WARNING": "amber", "ACTIVE": "cyan", "ONLINE": "green"}[self.status_text]

    def live_values(self):
        return compute_live_values(
            self.name, self.online, self.output, self.voltage_setpoint, self.current_limit,
            featured=self.featured, featured_v=data.FEATURED_VOLTAGE,
            featured_i=data.FEATURED_CURRENT, featured_p=data.FEATURED_POWER,
        )

    def visa(self):
        return f"TCPIP0::192.168.10.{20 + self.slot}::inst0::INSTR"

    def to_dict(self):
        v, i, p = self.live_values()
        rack_meta = data.RACK_META[self.rack]
        return {
            "name": self.name, "rack": self.rack, "slot": self.slot,
            "pos": f"{rack_meta['name']} · S{self.slot}",
            "online": self.online, "output": self.output, "alarm": self.alarm,
            "statusText": self.status_text, "statusColor": self.status_color,
            "voltage": v, "current": i, "power": p,
            "voltageSetpoint": self.voltage_setpoint, "currentLimit": self.current_limit,
            "featured": self.featured,
        }

    def to_detail_dict(self):
        base = self.to_dict()
        base.update({
            "connection": "CONNECTED" if self.online else "OFFLINE",
            "visa": self.visa(),
            "lastComm": now_hhmmss() if self.online else "—",
            "firmware": "E4360A · v3.1.2",
            "mode": "SIMULATION",
            "deviceState": "Stable" if self.output else "Output Disabled",
        })
        return base


class Run:
    def __init__(self, seed):
        self.__dict__.update(seed)
        self.events = list(data.RUN_EVENTS_SEED.get(self.id, []))
        self._task = None

    def to_dict(self):
        return {
            "id": self.id, "scenario": self.scenario, "version": self.version,
            "status": self.status, "dry": self.dry, "prog": self.prog,
            "targets": self.targets, "by": self.by, "started": self.started,
            "finished": self.finished, "dur": self.dur,
        }

    def to_detail_dict(self):
        d = self.to_dict()
        d["events"] = self.events
        return d


class AppState:
    def __init__(self):
        self.units = {name: Unit(name, rack, slot, online, output, alarm)
                      for name, rack, slot, online, output, alarm in data.RAW_UNITS}
        self.alarms = [dict(a, ackd=False) for a in data.ALARMS_SEED]
        self.history = [dict(h) for h in data.HISTORY_SEED]
        self.runs = {r["id"]: Run(r) for r in data.RUNS_SEED}
        self.assign = dict(data.RACK_B_ASSIGN_SEED)
        self.palette = list(data.RACK_B_PALETTE_SEED)
        self.node_props_extra = {}

    # ---------- racks / units ----------
    def racks(self):
        out = []
        for rid, meta in data.RACK_META.items():
            us = sorted([u for u in self.units.values() if u.rack == rid], key=lambda u: u.slot)
            out.append({
                "id": rid, "name": meta["name"], "loc": meta["loc"], "cap": meta["cap"],
                "count": len(us), "onCount": sum(1 for u in us if u.online),
                "units": [u.to_dict() for u in us],
            })
        return out

    def summary(self):
        units = list(self.units.values())
        online = sum(1 for u in units if u.online)
        active_out = sum(1 for u in units if u.online and u.output)
        total_p = sum(u.live_values()[2] for u in units if u.online and u.output)
        running = sum(1 for r in self.runs.values() if r.status == "Running")
        active_alarms = sum(1 for a in self.alarms if a["active"] and not a["ackd"])
        crit_alarms = sum(1 for a in self.alarms if a["active"] and a["sev"] == "critical" and not a["ackd"])
        return {
            "configuredUnits": len(units), "onlineDevices": online, "activeOutputs": active_out,
            "totalPowerW": round(total_p, 1), "runningScenarios": running,
            "activeAlarms": active_alarms, "criticalAlarms": crit_alarms,
        }

    def get_unit(self, name):
        return self.units.get(name)

    def log(self, user, dev, tpl, st="OK", lat="—", rb=True):
        entry = {"t": now_hhmmss(), "user": user, "dev": dev, "tpl": tpl, "st": st, "lat": lat,
                 "rb": rb, "cid": next_corr_id()}
        self.history.insert(0, entry)
        return entry

    # ---------- measurements ----------
    def telemetry(self, unit_name, rng):
        n = RANGE_N.get(rng, 48)
        seed = RANGE_SEED.get(rng, 2)
        return {
            "t": rng, "n": n,
            "v": gen_series(28, 1.4, 24, 32, n, seed),
            "i": gen_series(4.2, 0.9, 0, 6, n, seed * 1.4),
            "p": gen_series(117, 16, 0, 150, n, seed * 0.7),
        }

    def measurements(self, unit_names, rng):
        series = []
        for idx, name in enumerate(unit_names):
            u = self.units.get(name)
            seed = RANGE_SEED.get(rng, 2) + idx * 1.7
            n = RANGE_N.get(rng, 48)
            series.append({
                "name": name, "statusColor": u.status_color if u else "cyan",
                "v": gen_series(28, 1.5, 24, 32, n, seed),
                "i": gen_series(4.2, 0.9, 0, 6, n, seed * 1.4),
                "p": gen_series(117, 18, 0, 150, n, seed * 0.7),
            })
        rows = []
        for ui, name in enumerate(unit_names):
            u = self.units.get(name)
            if not u:
                continue
            h = 0
            for ch in name:
                h = (h * 31 + ord(ch)) % 997
            for k, ts in enumerate(["14:33:00", "14:32:30", "14:32:00"]):
                hh = h + k * 17
                v = 27.6 + (hh % 9) * 0.14
                cur = 3.9 + (hh % 6) * 0.12
                q = "interp" if (k == 2 and ui == 1) else "ok"
                rows.append({
                    "unit": name, "time": ts, "v": round(v, 3), "i": round(cur, 3), "p": round(v * cur, 2),
                    "out": "ON" if u.output else "OFF", "q": q,
                })
        return {"series": series, "rows": rows, "count": len(unit_names),
                "sampleText": f"{RANGE_N.get(rng, 48)} samples · {rng}"}

    # ---------- alarms ----------
    def alarms_view(self, flt):
        rows = [a for a in self.alarms if flt == "All" or (a["active"] if flt == "Active" else not a["active"])]
        return {
            "rows": rows,
            "activeCount": sum(1 for a in self.alarms if a["active"]),
            "critCount": sum(1 for a in self.alarms if a["sev"] == "critical" and a["active"]),
        }

    def ack_alarm(self, alarm_id):
        for a in self.alarms:
            if a["id"] == alarm_id:
                a["ackd"] = True
                return a
        return None

    # ---------- history ----------
    def history_view(self, flt, limit=200):
        rows = [h for h in self.history if flt == "All" or h["st"] == flt]
        return {"rows": rows[:limit], "total": len(self.history), "shown": min(limit, len(rows))}

    # ---------- runs ----------
    def create_run(self, scenario, version, targets, by="a.ng", dry=False):
        seq = len(self.runs) + 8843
        run_id = f"RUN-{seq}"
        seed = {"id": run_id, "scenario": scenario, "version": version, "status": "Queued",
                "dry": dry, "prog": 0, "targets": targets, "by": by,
                "started": now_hhmmss(), "finished": "—", "dur": "0s"}
        r = Run(seed)
        self.runs[run_id] = r
        return run_id

    def runs_view(self, flt):
        rows = [r.to_dict() for r in self.runs.values() if flt == "All" or r.status == flt]
        return rows

    def run_detail(self, run_id):
        r = self.runs.get(run_id)
        return r.to_detail_dict() if r else None

    async def start_run(self, run_id, on_tick=None):
        r = self.runs.get(run_id)
        if not r or r.status == "Running":
            return
        r.status, r.prog = "Running", 0
        r.started, r.finished = now_hhmmss(), "—"
        r.events = [{"t": now_hhmmss(), "node": "start", "lvl": "info",
                     "m": f"Run accepted — scenario {r.version} approved · {len(r.targets)} target(s)"}]
        steps = ["profile", "setv", "enable", "wait", "read", "thresh", "record", "disable", "end"]

        async def _drive():
            for idx, step in enumerate(steps):
                await asyncio.sleep(1.2)
                if r.status != "Running":
                    return
                r.prog = round((idx + 1) / len(steps) * 100)
                r.events.append({"t": now_hhmmss(), "node": step, "lvl": "ok", "m": f"{step} → completed"})
            r.status, r.prog, r.finished = "Completed", 100, now_hhmmss()
            r.events.append({"t": now_hhmmss(), "node": "end", "lvl": "ok", "m": "Run completed"})

        r._task = asyncio.create_task(_drive())

    def pause_run(self, run_id):
        r = self.runs.get(run_id)
        if r and r.status == "Running":
            return {"ok": True, "message": f"Pause requested · {run_id}"}
        return {"ok": False, "message": "Run is not active"}

    def abort_run(self, run_id):
        r = self.runs.get(run_id)
        if not r or r.status != "Running":
            return {"ok": False, "message": "Run is not active"}
        if r._task:
            r._task.cancel()
        r.status, r.finished = "Aborted", now_hhmmss()
        r.events.append({"t": now_hhmmss(), "node": "shutdown", "lvl": "err",
                          "m": "Abort dispatched · safe_shutdown on all targets"})
        return {"ok": True, "message": f"Abort dispatched · {run_id}"}

    # ---------- scenario builder ----------
    def scenario_graph(self):
        nodes = [dict(n) for n in data.NODE_DEFS]
        edges = [{"from": a, "to": b, "kind": k, "fail": f} for a, b, k, f in data.EDGE_DEFS]
        return {"scenario": data.SCENARIO, "nodes": nodes, "edges": edges, "palette": data.NODE_PALETTE}

    def node_props(self, node_id):
        if node_id in data.NODE_PROPS_OVERRIDE:
            return data.NODE_PROPS_OVERRIDE[node_id]
        n = next((n for n in data.NODE_DEFS if n["id"] == node_id), None)
        if not n:
            return None
        return {
            "name": n["label"], "target": "Scenario default group",
            "params": [["Type", n["type"]], ["Value", n.get("sub", "—")]],
            "delay": "0 ms", "timeout": "5 000 ms", "retry": "0 retries",
            "fail": "Abort scenario", "comments": "—",
        }

    # ---------- configuration ----------
    def config_units(self):
        out = []
        for u in list(self.units.values())[:8]:
            out.append({
                "name": u.name, "rack": data.RACK_META[u.rack]["name"], "slot": f"S{u.slot}",
                "visa": u.visa(), "poll": "500 ms", "enabled": u.online,
            })
        return out

    def rack_slots(self, rack_id="B"):
        slots = []
        for i in range(1, 8):
            key = f"{rack_id}{i}"
            occ = self.assign.get(key, "")
            slots.append({"key": key, "label": f"Slot {i}", "occ": occ, "empty": not occ})
        return slots

    def assign_unit(self, slot, unit_name):
        if self.assign.get(slot):
            freed = self.assign[slot]
            if freed not in self.palette:
                self.palette.append(freed)
        self.assign[slot] = unit_name
        if unit_name in self.palette:
            self.palette.remove(unit_name)
        return {"assign": self.assign, "palette": self.palette}


state = AppState()
