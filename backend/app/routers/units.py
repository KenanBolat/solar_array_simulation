from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db
from ..models import OutputRequest, SetpointRequest, ProfileRequest, TerminalExecuteRequest, CreateUnitRequest, NetworkRequest, OnlineRequest

router = APIRouter(prefix="/api/units", tags=["units"])

USER = "a.ng"


def _unit_or_404(db: Session, name: str):
    u = state.get_unit(db, name)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return u


@router.get("")
def list_units(db: Session = Depends(get_db)):
    return [state.unit_to_dict(u) for u in state.list_units(db)]


@router.post("")
def create_unit(body: CreateUnitRequest, db: Session = Depends(get_db)):
    if state.get_unit(db, body.name):
        raise HTTPException(409, f"Unit {body.name} already exists")
    try:
        u = state.create_unit(db, body.name, body.rack, ip_address=body.ipAddress or "",
                               mac_address=body.macAddress or "", poll_ms=body.pollMs, slot=body.slot)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return state.unit_to_detail_dict(u)


@router.post("/{name}/simulate-online")
def simulate_online(name: str, body: OnlineRequest, db: Session = Depends(get_db)):
    """Comms-loss simulator, independent of enable/disable — see
    state.set_unit_online. Not something a real driver would expose; this is
    purely for exercising the null-on-no-reading path without real hardware."""
    u = state.set_unit_online(db, name, body.online)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return state.unit_to_detail_dict(u)


@router.post("/{name}/network")
def update_network(name: str, body: NetworkRequest, db: Session = Depends(get_db)):
    u = state.update_unit_network(db, name, body.ipAddress, body.macAddress)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return state.unit_to_detail_dict(u)


@router.delete("/{name}")
def delete_unit(name: str, db: Session = Depends(get_db)):
    if not state.delete_unit(db, name):
        raise HTTPException(404, f"Unknown unit {name}")
    return {"ok": True}


@router.post("/{name}/enable")
def enable_unit(name: str, db: Session = Depends(get_db)):
    u = state.set_unit_enabled(db, name, True)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return state.unit_to_detail_dict(u)


@router.post("/{name}/disable")
def disable_unit(name: str, db: Session = Depends(get_db)):
    u = state.set_unit_enabled(db, name, False)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return state.unit_to_detail_dict(u)


@router.get("/{name}")
def get_unit(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    return state.unit_to_detail_dict(u)


@router.get("/{name}/telemetry")
def get_telemetry(name: str, range: str = "30 min", db: Session = Depends(get_db)):
    _unit_or_404(db, name)
    return state.telemetry(db, name, range)


@router.post("/{name}/output")
def set_output(name: str, body: OutputRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    state.set_output(db, name, body.on)
    entry = state.log_command(db, USER, name, "output_on" if body.on else "output_off", lat="38 ms")
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/setpoint")
def set_setpoint(name: str, body: SetpointRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    entries = []
    if body.voltage is not None:
        state.set_setpoint(db, name, body.voltage, None)
        entries.append(state.log_command(db, USER, name, "set_voltage", lat="41 ms"))
    if body.currentLimit is not None:
        state.set_setpoint(db, name, None, body.currentLimit)
        entries.append(state.log_command(db, USER, name, "set_current_limit", lat="44 ms"))
    return {"unit": state.unit_to_detail_dict(u), "log": entries}


@router.post("/{name}/shutdown")
def safe_shutdown(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    state.shutdown_unit(db, name)
    entry = state.log_command(db, USER, name, "safe_shutdown", lat="120 ms")
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/refresh")
def refresh_measurement(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    entry = state.log_command(db, "system", name, "read_measurements", lat="22 ms", rb=False)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/identify")
def identify(name: str, db: Session = Depends(get_db)):
    _unit_or_404(db, name)
    entry = state.log_command(db, USER, name, "identify", lat="18 ms")
    return {"idn": "Keysight,E4360A,SIM-0007,3.1.2 (simulated)", "log": entry}


@router.post("/{name}/apply-profile")
def apply_profile(name: str, body: ProfileRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    entry = state.log_command(db, USER, name, "apply_profile", lat="66 ms")
    return {"unit": state.unit_to_detail_dict(u), "log": entry, "profile": body.profile}


@router.post("/{name}/terminal/execute")
def terminal_execute(name: str, body: TerminalExecuteRequest, db: Session = Depends(get_db)):
    """Executes a resolved guided-terminal command. Vocabulary matching, hint
    completion and history navigation stay client-side (pure UI concerns);
    anything that actually changes device state or needs to be audited comes
    through here so it lands in the same append-only log as every other
    control surface.
    """
    u = _unit_or_404(db, name)
    if body.act == "on":
        state.set_output(db, name, True)
        entry = state.log_command(db, USER, name, "output_on", lat="30 ms")
        return {"line": f"output ON — array energised · completed · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "off":
        state.set_output(db, name, False)
        entry = state.log_command(db, USER, name, "output_off", lat="28 ms")
        return {"line": f"output OFF — array de-energised · completed · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "shutdown":
        state.shutdown_unit(db, name)
        entry = state.log_command(db, USER, name, "safe_shutdown", lat="120 ms")
        return {"line": f"safe shutdown — output disabled, unit to standby · completed · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "read":
        v, i, p = state.unit_live_values(u)
        entry = state.log_command(db, "system", name, "read_measurements",
                                   lat="42 ms", rb=False, st="OK" if v is not None else "ERR")
        if v is None:
            return {"line": f"read_measurements → no reading — comms down · 42 ms · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
        return {"line": f"read_measurements → {v:.3f} V, {i:.3f} A, {p:.2f} W · 42 ms · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "status":
        v, i, p = state.unit_live_values(u)
        if v is None:
            return {"line": f"comms down · no cached reading · alarm {u.alarm} · simulation", "unit": state.unit_to_dict(u)}
        return {"line": (f"output {'ON' if u.output else 'OFF'} · {v:.3f} V · limit {u.current_limit:.2f} A\n"
                          f"state {'stable' if u.output else 'output_disabled'} · comms healthy · alarm {u.alarm} · simulation"),
                "unit": state.unit_to_dict(u)}
    if body.act == "idn":
        entry = state.log_command(db, USER, name, "identify", lat="18 ms")
        return {"line": f"identify → Keysight,E4360A,SIM-0007,3.1.2 · 18 ms · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "setv":
        if body.value is None:
            raise HTTPException(400, "value required")
        state.set_setpoint(db, name, body.value, None)
        entry = state.log_command(db, USER, name, "set_voltage", lat="41 ms")
        return {"line": f"set_voltage {body.value:.2f} V → ACK · readback verified · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    if body.act == "seti":
        if body.value is None:
            raise HTTPException(400, "value required")
        state.set_setpoint(db, name, None, body.value)
        entry = state.log_command(db, USER, name, "set_current_limit", lat="44 ms")
        return {"line": f"set_current_limit {body.value:.2f} A → ACK · readback verified · corr {entry['cid']}", "unit": state.unit_to_dict(u)}
    raise HTTPException(400, f"Unsupported action {body.act}")
