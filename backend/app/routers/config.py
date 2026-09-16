from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import data, state
from ..db import get_db
from ..models import AssignRequest

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/racks")
def config_racks(db: Session = Depends(get_db)):
    return state.config_racks(db)


@router.get("/units")
def config_units(db: Session = Depends(get_db)):
    return state.config_units(db)


@router.get("/limits")
def config_limits():
    return data.OPERATIONAL_LIMITS


@router.get("/rack-editor")
def rack_editor(rack: str = "A", db: Session = Depends(get_db)):
    return {"slots": state.rack_slots(db, rack), "palette": state.unassigned_units(db, rack)}


@router.post("/rack-editor/assign")
def assign(body: AssignRequest, db: Session = Depends(get_db)):
    try:
        return state.assign_unit(db, body.slot, body.unitName)
    except ValueError as e:
        raise HTTPException(400, str(e))
