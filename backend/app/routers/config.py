from fastapi import APIRouter, HTTPException
from .. import data
from ..state import state
from ..models import AssignRequest

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/racks")
def config_racks():
    return [{"id": rid, **meta, "unitsAssigned": sum(1 for v in state.assign.values() if v)}
            for rid, meta in data.RACK_META.items()]


@router.get("/units")
def config_units():
    return state.config_units()


@router.get("/limits")
def config_limits():
    return data.OPERATIONAL_LIMITS


@router.get("/rack-editor")
def rack_editor(rack: str = "B"):
    return {"slots": state.rack_slots(rack), "palette": state.palette}


@router.post("/rack-editor/assign")
def assign(body: AssignRequest):
    if body.slot[0] not in data.RACK_META:
        raise HTTPException(400, "Unknown rack")
    return state.assign_unit(body.slot, body.unitName)
