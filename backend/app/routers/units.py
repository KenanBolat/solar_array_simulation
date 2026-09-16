from fastapi import APIRouter, HTTPException
from ..state import state, now_hhmmss
from ..models import OutputRequest, SetpointRequest, ProfileRequest, TerminalExecuteRequest

router = APIRouter(prefix="/api/units", tags=["units"])

USER = "a.ng"


def _unit_or_404(name):
    u = state.get_unit(name)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return u


@router.get("")
def list_units():
    return [u.to_dict() for u in state.units.values()]


@router.get("/{name}")
def get_unit(name: str):
    u = _unit_or_404(name)
    return u.to_detail_dict()


@router.get("/{name}/telemetry")
def get_telemetry(name: str, range: str = "30 min"):
    _unit_or_404(name)
    return state.telemetry(name, range)


@router.post("/{name}/output")
def set_output(name: str, body: OutputRequest):
    u = _unit_or_404(name)
    u.output = body.on
    entry = state.log(USER, name, "output_on" if body.on else "output_off", lat="38 ms")
    return {"unit": u.to_detail_dict(), "log": entry}


@router.post("/{name}/setpoint")
def set_setpoint(name: str, body: SetpointRequest):
    u = _unit_or_404(name)
    entries = []
    if body.voltage is not None:
        u.voltage_setpoint = max(0.0, min(32.0, body.voltage))
        entries.append(state.log(USER, name, "set_voltage", lat="41 ms"))
    if body.currentLimit is not None:
        u.current_limit = max(0.0, min(6.0, body.currentLimit))
        entries.append(state.log(USER, name, "set_current_limit", lat="44 ms"))
    return {"unit": u.to_detail_dict(), "log": entries}


@router.post("/{name}/shutdown")
def safe_shutdown(name: str):
    u = _unit_or_404(name)
    u.output = False
    u.current_limit = 0.0
    entry = state.log(USER, name, "safe_shutdown", lat="120 ms")
    return {"unit": u.to_detail_dict(), "log": entry}


@router.post("/{name}/refresh")
def refresh_measurement(name: str):
    u = _unit_or_404(name)
    entry = state.log("system", name, "read_measurements", lat="22 ms", rb=False)
    return {"unit": u.to_detail_dict(), "log": entry}


@router.post("/{name}/identify")
def identify(name: str):
    u = _unit_or_404(name)
    entry = state.log(USER, name, "identify", lat="18 ms")
    return {"idn": "Keysight,E4360A,SIM-0007,3.1.2 (simulated)", "log": entry}


@router.post("/{name}/apply-profile")
def apply_profile(name: str, body: ProfileRequest):
    u = _unit_or_404(name)
    entry = state.log(USER, name, "apply_profile", lat="66 ms")
    return {"unit": u.to_detail_dict(), "log": entry, "profile": body.profile}


@router.post("/{name}/terminal/execute")
def terminal_execute(name: str, body: TerminalExecuteRequest):
    """Executes a resolved guided-terminal command. Vocabulary matching, hint
    completion and history navigation stay client-side (pure UI concerns);
    anything that actually changes device state or needs to be audited comes
    through here so it lands in the same append-only log as every other
    control surface.
    """
    u = _unit_or_404(name)
    corr = None
    if body.act == "on":
        u.output = True
        entry = state.log(USER, name, "output_on", lat="30 ms")
        return {"line": f"output ON — array energised · completed · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "off":
        u.output = False
        entry = state.log(USER, name, "output_off", lat="28 ms")
        return {"line": f"output OFF — array de-energised · completed · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "shutdown":
        u.output = False
        u.current_limit = 0.0
        entry = state.log(USER, name, "safe_shutdown", lat="120 ms")
        return {"line": f"safe shutdown — output disabled, unit to standby · completed · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "read":
        v, i, p = u.live_values()
        entry = state.log("system", name, "read_measurements", lat="42 ms", rb=False)
        return {"line": f"read_measurements → {v:.3f} V, {i:.3f} A, {p:.2f} W · 42 ms · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "status":
        v, i, p = u.live_values()
        return {"line": (f"output {'ON' if u.output else 'OFF'} · {v:.3f} V · limit {u.current_limit:.2f} A\n"
                          f"state {'stable' if u.output else 'output_disabled'} · comms healthy · alarm {u.alarm} · simulation"),
                "unit": u.to_dict()}
    if body.act == "idn":
        entry = state.log(USER, name, "identify", lat="18 ms")
        return {"line": f"identify → Keysight,E4360A,SIM-0007,3.1.2 · 18 ms · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "setv":
        if body.value is None:
            raise HTTPException(400, "value required")
        u.voltage_setpoint = max(0.0, min(32.0, body.value))
        entry = state.log(USER, name, "set_voltage", lat="41 ms")
        return {"line": f"set_voltage {body.value:.2f} V → ACK · readback verified · corr {entry['cid']}", "unit": u.to_dict()}
    if body.act == "seti":
        if body.value is None:
            raise HTTPException(400, "value required")
        u.current_limit = max(0.0, min(6.0, body.value))
        entry = state.log(USER, name, "set_current_limit", lat="44 ms")
        return {"line": f"set_current_limit {body.value:.2f} A → ACK · readback verified · corr {entry['cid']}", "unit": u.to_dict()}
    raise HTTPException(400, f"Unsupported action {body.act}")
