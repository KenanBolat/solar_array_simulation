from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, state
from ..db import get_db
from ..models import AssignRequest, CreateRackRequest, UpdateRackRequest
from ..seed import FLEET_FILE, apply_fleet, load_fleet

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/racks")
def config_racks(db: Session = Depends(get_db)):
    return state.config_racks(db)


@router.post("/racks")
def create_rack(body: CreateRackRequest, db: Session = Depends(get_db)):
    try:
        rack = state.create_rack(db, body.id, body.name, body.loc, body.cap)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": rack.id, "name": rack.name, "loc": rack.loc, "cap": rack.cap}


@router.patch("/racks/{rack_id}")
def update_rack(rack_id: str, body: UpdateRackRequest, db: Session = Depends(get_db)):
    try:
        rack = state.update_rack(db, rack_id, body.name, body.loc, body.cap)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not rack:
        raise HTTPException(404, f"Unknown rack {rack_id}")
    return {"id": rack.id, "name": rack.name, "loc": rack.loc, "cap": rack.cap}


@router.delete("/racks/{rack_id}")
def delete_rack(rack_id: str, db: Session = Depends(get_db)):
    try:
        ok = state.delete_rack(db, rack_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not ok:
        raise HTTPException(404, f"Unknown rack {rack_id}")
    return {"ok": True}


@router.get("/units")
def config_units(db: Session = Depends(get_db)):
    return state.config_units(db)


@router.get("/limits")
def config_limits():
    return data.OPERATIONAL_LIMITS


@router.get("/profiles")
def config_profiles():
    return [{"name": k, **v} for k, v in data.SAS_PROFILES.items()]


@router.get("/fleet")
def get_fleet():
    """What the fleet file currently says, so the UI can show whether the
    stored units still match it."""
    return {"file": str(FLEET_FILE), **load_fleet()}


@router.post("/fleet/apply")
def apply_fleet_file(db: Session = Depends(get_db)):
    return apply_fleet(db)


@router.get("/rack-editor")
def rack_editor(rack: str = "A", db: Session = Depends(get_db)):
    return {"slots": state.rack_slots(db, rack), "palette": state.unassigned_units(db, rack)}


@router.post("/rack-editor/assign")
def assign(body: AssignRequest, db: Session = Depends(get_db)):
    try:
        return state.assign_unit(db, body.slot, body.unitName)
    except ValueError as e:
        raise HTTPException(400, str(e))
