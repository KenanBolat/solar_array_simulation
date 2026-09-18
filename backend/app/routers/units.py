from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, state
from ..db import get_db
from ..models import (CreateInstrumentRequest, CreateUnitRequest, ModeRequest, NetworkRequest, OutputRequest,
                      ProfileRequest, SasCurveRequest, SetpointRequest, StateSlotRequest, TerminalExecuteRequest)
from ..diagnostics import diagnose, host_addresses
from ..poller import measure_unit, reset_backoff
from ..scpi import TRANSPORTS, CommandResult, Instrument, close_all_sessions, close_session

router = APIRouter(prefix="/api/units", tags=["units"])

USER = "a.ng"
MAX_V = data.OPERATIONAL_LIMITS["max_voltage_v"]
MAX_I = data.OPERATIONAL_LIMITS["max_current_a"]


def _unit_or_404(db: Session, name: str):
    u = state.get_unit(db, name)
    if not u:
        raise HTTPException(404, f"Unknown unit {name}")
    return u


def _dispatch(db: Session, u, tpl: str, op, user: str = USER):
    """Send one documented operation to the unit's instrument, record exactly
    what happened in the audit log, and only then let the caller mirror the
    confirmed state. Anything but OK surfaces as 502 with the instrument's
    own error text (or the transport failure) and the correlation id."""
    result: CommandResult = op(Instrument.for_unit(u))
    entry = state.log_command(db, user, u.name, tpl, result)
    if not result.ok:
        raise HTTPException(502, f"{tpl} · {result.describe()} · corr {entry['cid']}")
    return result, entry


def _soft_limit(value: float, hi: float, what: str):
    if value < 0 or value > hi:
        raise HTTPException(400, f"{what} {value:g} is outside the platform soft limit 0 – {hi:g}")


def _validate_addressing(transport: str | None, channel: int | None):
    if transport is not None and transport not in TRANSPORTS:
        raise HTTPException(400, f"transport must be one of {', '.join(TRANSPORTS)}")
    if channel is not None and not 1 <= channel <= 2:
        raise HTTPException(400, "channel must be 1 or 2 (an E4360 mainframe holds two output modules)")


@router.get("")
def list_units(db: Session = Depends(get_db)):
    return [state.unit_to_dict(u) for u in state.list_units(db)]


@router.post("/instrument")
def create_instrument(body: CreateInstrumentRequest, db: Session = Depends(get_db)):
    """Add a mainframe: one unit per output channel, named <name> for channel 1
    and <name>-CH<n> after that (all displayed as '<name> (@n)'). With
    channels="auto" the instrument is asked SYST:CHAN? first, so the fleet
    matches the hardware rather than an assumption."""
    _validate_addressing(body.transport, None)
    if state.get_unit(db, body.name):
        raise HTTPException(409, f"Unit {body.name} already exists")

    count, detected = 2, None
    if body.channels == "auto":
        probe = Instrument(body.ipAddress, body.scpiPort,
                           "vxi11" if body.transport == "auto" else body.transport, 1)
        res = probe.channel_count()
        if not res.ok and body.transport == "auto":  # auto transport: try the socket path too
            probe = Instrument(body.ipAddress, body.scpiPort, "socket", 1)
            res = probe.channel_count()
        if res.ok and res.response:
            try:
                count = detected = max(1, min(2, int(float(res.response))))
            except ValueError:
                count = 1
        else:
            count = 1  # couldn't ask: configure channel 1 only, Discover channels can add the rest later
    else:
        try:
            count = max(1, min(2, int(body.channels)))
        except ValueError:
            raise HTTPException(400, "channels must be 'auto', '1' or '2'")

    created = []
    for ch in range(1, count + 1):
        unit_name = body.name if ch == 1 else f"{body.name}-CH{ch}"
        try:
            u = state.create_unit(db, unit_name, body.rack, ip_address=body.ipAddress,
                                   mac_address=body.macAddress or "", scpi_port=body.scpiPort,
                                   transport=body.transport, channel=ch, poll_ms=body.pollMs,
                                   mainframe_name=body.name)
        except ValueError as e:
            raise HTTPException(400, f"channel {ch}: {e}")
        created.append(state.unit_to_dict(u))
    return {"instrument": body.name, "detectedChannels": detected, "created": created}


@router.post("/discover-channels")
def discover_channels(db: Session = Depends(get_db)):
    """Ask every distinct mainframe how many output channels it has
    (SYST:CHAN?) and create a unit row for any channel not configured yet, so
    Measurements shows all of them. Existing units are never modified."""
    # One mainframe is one ADDRESS, not one IP: two units can share an IP and
    # differ by port (as the bundled emulators do), and that's two instruments.
    seen: dict[tuple, list] = {}
    for u in state.list_units(db):
        if u.ip_address:
            seen.setdefault((u.ip_address, u.scpi_port, u.transport), []).append(u)
    created, report = [], []
    for (ip, port, transport), units_here in seen.items():
        probe = units_here[0]
        label = ip if transport != "socket" else f"{ip}:{port}"
        res = Instrument.for_unit(probe).channel_count()
        if not res.ok or not res.response:
            report.append({"mainframe": label, "channels": None, "error": res.describe()})
            continue
        try:
            count = int(float(res.response))
        except ValueError:
            report.append({"mainframe": label, "channels": None, "error": f"unparsable reply {res.response!r}"})
            continue
        have = {u.channel for u in units_here}
        for ch in range(1, count + 1):
            if ch in have:
                continue
            base = probe.name.split("-CH")[0]
            new_name = f"{base}-CH{ch}"
            if state.get_unit(db, new_name):
                continue
            try:
                u = state.create_unit(db, new_name, probe.rack_id, ip_address=ip, mac_address=probe.mac_address,
                                       scpi_port=port, transport=transport, channel=ch, poll_ms=probe.poll_ms,
                                       mainframe_name=state.instrument_name(probe))
            except ValueError as e:
                report.append({"mainframe": label, "channels": count, "error": f"channel {ch}: {e}"})
                continue
            created.append(u.name)
        report.append({"mainframe": label, "channels": count, "error": None})
    return {"created": created, "mainframes": report}


@router.post("/reset-connections")
def reset_connections(db: Session = Depends(get_db)):
    """Kill every session this app holds, forget the retry backoff, and re-poll
    all enabled units right now. Sessions held by other clients survive this —
    only the instrument can drop those (POST /{name}/reboot)."""
    dropped = close_all_sessions()
    reset_backoff()
    out = []
    for u in state.list_units(db):
        if not u.enabled:
            continue
        result, reading, resolved = measure_unit(u.ip_address, u.scpi_port, u.transport, u.channel)
        if resolved and u.transport == "auto":
            u.transport = resolved
            u.visa = state.derive_visa(u.ip_address, u.scpi_port, resolved)
        state.apply_reading(db, u, result, reading)
        out.append({"name": u.name, "online": u.online, "transport": u.transport, "lastError": u.last_error or None})
    return {"dropped": dropped, "units": out}


@router.post("")
def create_unit(body: CreateUnitRequest, db: Session = Depends(get_db)):
    if state.get_unit(db, body.name):
        raise HTTPException(409, f"Unit {body.name} already exists")
    _validate_addressing(body.transport, body.channel)
    try:
        u = state.create_unit(db, body.name, body.rack, ip_address=body.ipAddress or "",
                               mac_address=body.macAddress or "", scpi_port=body.scpiPort,
                               transport=body.transport, channel=body.channel,
                               poll_ms=body.pollMs, slot=body.slot)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return state.unit_to_detail_dict(u)


@router.post("/{name}/network")
def update_network(name: str, body: NetworkRequest, db: Session = Depends(get_db)):
    _validate_addressing(body.transport, body.channel)
    u = state.update_unit_network(db, name, body.ipAddress, body.macAddress, body.scpiPort,
                                  body.transport, body.channel)
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
    return state.unit_to_detail_dict(_unit_or_404(db, name))


@router.get("/{name}/telemetry")
def get_telemetry(name: str, range: str = "30 min", db: Session = Depends(get_db)):
    _unit_or_404(db, name)
    return state.telemetry(db, name, range)


# ---------- commands: every one of these talks to the instrument ----------
@router.post("/{name}/output")
def set_output(name: str, body: OutputRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    _, entry = _dispatch(db, u, "output_on" if body.on else "output_off", lambda i: i.set_output(body.on))
    state.mirror_output(db, name, body.on)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/setpoint")
def set_setpoint(name: str, body: SetpointRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    entries = []
    if body.voltage is not None:
        _soft_limit(body.voltage, MAX_V, "Voltage")
        _, e = _dispatch(db, u, "set_voltage", lambda i: i.set_voltage(body.voltage))
        state.mirror_setpoint(db, name, voltage=body.voltage)
        entries.append(e)
    if body.currentLimit is not None:
        _soft_limit(body.currentLimit, MAX_I, "Current limit")
        _, e = _dispatch(db, u, "set_current_limit", lambda i: i.set_current(body.currentLimit))
        state.mirror_setpoint(db, name, current_limit=body.currentLimit)
        entries.append(e)
    return {"unit": state.unit_to_detail_dict(u), "log": entries}


@router.post("/{name}/mode")
def set_mode(name: str, body: ModeRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    mode = body.mode.upper()
    if mode not in ("FIX", "SAS"):
        raise HTTPException(400, "mode must be FIX or SAS")
    _, entry = _dispatch(db, u, f"set_mode_{mode.lower()}", lambda i: i.set_mode(mode))
    state.mirror_mode(db, name, mode)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/clear-protection")
def clear_protection(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    result, entry = _dispatch(db, u, "clear_protection", lambda i: i.clear_protection())
    try:
        state.sync_protection_alarms(db, u, int(float(result.response or "0")))
        db.commit()
    except ValueError:
        pass
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/sas-curve")
def set_sas_curve(name: str, body: SasCurveRequest, db: Session = Depends(get_db)):
    """The four coupled SAS parameters, sent in one program message so the
    instrument validates the curve as a whole and rejects it atomically."""
    u = _unit_or_404(db, name)
    try:
        state.check_soft_limits("SAS", body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    _, entry = _dispatch(db, u, "set_sas_curve",
                         lambda i: i.apply_sas_curve(body.isc, body.imp, body.vmp, body.voc))
    state.mirror_sas(db, name, body.isc, body.imp, body.vmp, body.voc)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/state/save")
def save_state(name: str, body: StateSlotRequest, db: Session = Depends(get_db)):
    """*SAV 0|1. The guide warns NVRAM has a finite write-cycle budget, so this
    is only ever an explicit operator action."""
    u = _unit_or_404(db, name)
    if body.slot not in (0, 1):
        raise HTTPException(400, "The instrument has two state locations: 0 and 1")
    _, entry = _dispatch(db, u, f"save_state_{body.slot}", lambda i: i.save_state(body.slot))
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/state/recall")
def recall_state(name: str, body: StateSlotRequest, db: Session = Depends(get_db)):
    """*RCL 0|1 — mainframe-wide, so a second channel on the same IP changes too."""
    u = _unit_or_404(db, name)
    if body.slot not in (0, 1):
        raise HTTPException(400, "The instrument has two state locations: 0 and 1")
    _, entry = _dispatch(db, u, f"recall_state_{body.slot}", lambda i: i.recall_state(body.slot))
    result, reading, _ = measure_unit(u.ip_address, u.scpi_port, u.transport, u.channel)
    state.apply_reading(db, u, result, reading)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/shutdown")
def safe_shutdown(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    _, entry = _dispatch(db, u, "safe_shutdown", lambda i: i.safe_shutdown())
    state.mirror_output(db, name, False)
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/reconnect")
def reconnect(name: str, db: Session = Depends(get_db)):
    """Drop the cached connection and poll immediately — the "try again now"
    button for a unit that reads unreachable."""
    u = _unit_or_404(db, name)
    close_session(u.visa)
    result, reading, resolved = measure_unit(u.ip_address, u.scpi_port, u.transport, u.channel)
    if resolved and u.transport == "auto":
        u.transport = resolved
        u.visa = state.derive_visa(u.ip_address, u.scpi_port, resolved)
    state.apply_reading(db, u, result, reading)
    return {"unit": state.unit_to_detail_dict(u), "result": result.describe()}


@router.post("/{name}/diagnose")
def diagnose_unit(name: str, db: Session = Depends(get_db)):
    """Probe this unit's address from the backend host. The app's own session
    is closed first so the probe doesn't compete with it for the instrument's
    single socket slot; the poller reconnects afterwards."""
    u = _unit_or_404(db, name)
    close_session(u.visa)
    report = diagnose(u.ip_address, u.scpi_port, u.channel)
    report.update({"unit": name, "ip": u.ip_address, "transport": u.transport, "from": host_addresses()})
    return report


@router.post("/{name}/reboot")
def reboot_unit(name: str, db: Session = Depends(get_db)):
    """SYSTem:REBoot — the documented way to make the mainframe drop every
    session on it (including a telnet held on another machine). Output goes
    OFF; the unit answers again after ~30 s."""
    u = _unit_or_404(db, name)
    if u.transport == "auto":
        raise HTTPException(409, "Transport not resolved yet — no path to this unit has answered, so nothing can carry the reboot")
    result = Instrument.for_unit(u).reboot()
    entry = state.log_command(db, USER, name, "system_reboot", result)
    if not result.ok:
        raise HTTPException(502, f"system_reboot · {result.describe()} · corr {entry['cid']}")
    u.online = False
    u.last_error = "SYST:REB sent — mainframe rebooting, allow ~30 s"
    u.last_voltage = u.last_current = u.last_power = None
    db.commit()
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/refresh")
def refresh_measurement(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    result, reading = Instrument.for_unit(u).measure()
    entry = state.log_command(db, USER, name, "read_measurements", result)
    state.apply_reading(db, u, result, reading)
    if not result.ok:
        raise HTTPException(502, f"read_measurements · {result.describe()} · corr {entry['cid']}")
    return {"unit": state.unit_to_detail_dict(u), "log": entry}


@router.post("/{name}/identify")
def identify(name: str, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    result, entry = _dispatch(db, u, "identify", lambda i: i.identify())
    if result.response:
        u.firmware = state.describe_identity(result.response)
        db.commit()
    return {"idn": result.response, "log": entry}


@router.post("/{name}/apply-profile")
def apply_profile(name: str, body: ProfileRequest, db: Session = Depends(get_db)):
    u = _unit_or_404(db, name)
    prof = data.SAS_PROFILES.get(body.profile)
    if not prof:
        raise HTTPException(404, f"Unknown profile {body.profile}")
    try:
        state.check_soft_limits("SAS", prof)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _, e1 = _dispatch(db, u, "set_mode_sas", lambda i: i.set_mode("SAS"))
    state.mirror_mode(db, name, "SAS")
    _, e2 = _dispatch(db, u, f"apply_profile:{body.profile}",
                      lambda i: i.apply_sas_curve(prof["isc"], prof["imp"], prof["vmp"], prof["voc"]))
    return {"unit": state.unit_to_detail_dict(u), "log": [e1, e2], "profile": body.profile}


@router.post("/{name}/terminal/execute")
def terminal_execute(name: str, body: TerminalExecuteRequest, db: Session = Depends(get_db)):
    """Executes a resolved guided-terminal command. Vocabulary matching, hint
    completion and history navigation stay client-side (pure UI concerns);
    anything that touches the instrument comes through here so it lands in
    the same append-only log as every other control surface."""
    u = _unit_or_404(db, name)

    if body.act in ("on", "off"):
        on = body.act == "on"
        r, e = _dispatch(db, u, "output_on" if on else "output_off", lambda i: i.set_output(on))
        state.mirror_output(db, name, on)
        return {"line": f"{r.sent} → OK · readback {r.response} · {r.latency_ms} ms · corr {e['cid']}",
                "unit": state.unit_to_dict(u)}
    if body.act == "shutdown":
        r, e = _dispatch(db, u, "safe_shutdown", lambda i: i.safe_shutdown())
        state.mirror_output(db, name, False)
        return {"line": f"safe shutdown → {r.sent} → OK · output confirmed OFF · corr {e['cid']}",
                "unit": state.unit_to_dict(u)}
    if body.act in ("read", "status"):
        result, reading = Instrument.for_unit(u).measure()
        entry = state.log_command(db, USER, name, "read_measurements", result)
        state.apply_reading(db, u, result, reading)
        if not result.ok or reading is None:
            raise HTTPException(502, f"read_measurements · {result.describe()} · corr {entry['cid']}")
        if body.act == "read":
            line = (f"MEAS:VOLT?/FETC:CURR? → {reading.voltage:.3f} V, {reading.current:.3f} A, "
                    f"{reading.power:.2f} W · {result.latency_ms} ms · corr {entry['cid']}")
        else:
            sp = (f" · VOLT? {reading.volt_set:.3f} V · CURR? {reading.curr_set:.3f} A"
                  if reading.volt_set is not None else "")
            line = (f"OUTP? {'ON' if reading.output else 'OFF'} · CURR:MODE? {reading.mode}{sp}\n"
                    f"STAT:QUES:COND? +{reading.questionable}"
                    f"{' (protection tripped)' if reading.questionable & state.PROTECTION_MASK else ' (no faults)'}"
                    f" · comms healthy · {result.latency_ms} ms")
        return {"line": line, "unit": state.unit_to_dict(u)}
    if body.act == "idn":
        r, e = _dispatch(db, u, "identify", lambda i: i.identify())
        return {"line": f"*IDN? → {r.response} · {r.latency_ms} ms · corr {e['cid']}", "unit": state.unit_to_dict(u)}
    if body.act in ("setv", "seti"):
        if body.value is None:
            raise HTTPException(400, "value required")
        if body.act == "setv":
            _soft_limit(body.value, MAX_V, "Voltage")
            r, e = _dispatch(db, u, "set_voltage", lambda i: i.set_voltage(body.value))
            state.mirror_setpoint(db, name, voltage=body.value)
        else:
            _soft_limit(body.value, MAX_I, "Current limit")
            r, e = _dispatch(db, u, "set_current_limit", lambda i: i.set_current(body.value))
            state.mirror_setpoint(db, name, current_limit=body.value)
        return {"line": f"{r.sent} → OK · readback {r.response} {'verified' if r.readback_ok else 'MISMATCH'}"
                        f" · {r.latency_ms} ms · corr {e['cid']}", "unit": state.unit_to_dict(u)}
    raise HTTPException(400, f"Unsupported action {body.act}")
