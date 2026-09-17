from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db
from ..models import ApplyPresetRequest, PresetEnableRequest, PresetRequest
from ..scpi import Instrument

router = APIRouter(prefix="/api/presets", tags=["presets"])

USER = "a.ng"


@router.get("")
def list_presets(db: Session = Depends(get_db)):
    return {"presets": state.list_presets(db), "max": state.MAX_PRESETS}


@router.post("")
def create_preset(body: PresetRequest, db: Session = Depends(get_db)):
    mode = body.mode.upper()
    if mode not in ("FIX", "SAS"):
        raise HTTPException(400, "mode must be FIX or SAS")
    try:
        return state.create_preset(db, body.name, mode, body.model_dump(), body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{preset_id}/enable")
def enable_preset(preset_id: int, body: PresetEnableRequest, db: Session = Depends(get_db)):
    p = state.set_preset_enabled(db, preset_id, body.enabled)
    if not p:
        raise HTTPException(404, "Unknown preset")
    return p


@router.delete("/{preset_id}")
def delete_preset(preset_id: int, db: Session = Depends(get_db)):
    if not state.delete_preset(db, preset_id):
        raise HTTPException(404, "Unknown preset")
    return {"ok": True}


@router.post("/{preset_id}/apply")
def apply_preset(preset_id: int, body: ApplyPresetRequest, db: Session = Depends(get_db)):
    """Dispatch a stored operating point to a unit: select the mode, then send
    the values for that mode. Each command is confirmed by readback and
    audited exactly like a manual one; the first failure stops the sequence
    and is returned with the instrument's own error."""
    from ..orm import Preset
    p = db.get(Preset, preset_id)
    if not p:
        raise HTTPException(404, "Unknown preset")
    if not p.enabled:
        raise HTTPException(409, f"Preset '{p.name}' is disabled")
    u = state.get_unit(db, body.unit)
    if not u:
        raise HTTPException(404, f"Unknown unit {body.unit}")
    try:  # same ceiling the manual controls use — a stored preset is not a bypass
        state.check_soft_limits(p.mode, {"volt": p.volt, "curr": p.curr, "isc": p.isc,
                                         "imp": p.imp, "vmp": p.vmp, "voc": p.voc})
    except ValueError as e:
        raise HTTPException(400, str(e))

    logs = []

    def step(tpl: str, op):
        result = op(Instrument.for_unit(u))
        entry = state.log_command(db, USER, u.name, tpl, result)
        logs.append(entry)
        if not result.ok:
            raise HTTPException(502, f"{tpl} · {result.describe()} · corr {entry['cid']}")
        return result

    step(f"preset:{p.name}:mode_{p.mode.lower()}", lambda i: i.set_mode(p.mode))
    state.mirror_mode(db, u.name, p.mode)
    if p.mode == "SAS":
        step(f"preset:{p.name}:sas_curve", lambda i: i.apply_sas_curve(p.isc, p.imp, p.vmp, p.voc))
        state.mirror_sas(db, u.name, p.isc, p.imp, p.vmp, p.voc)
    else:
        step(f"preset:{p.name}:set_voltage", lambda i: i.set_voltage(p.volt))
        step(f"preset:{p.name}:set_current_limit", lambda i: i.set_current(p.curr))
        state.mirror_setpoint(db, u.name, voltage=p.volt, current_limit=p.curr)
    return {"unit": state.unit_to_detail_dict(u), "preset": p.name, "log": logs}
