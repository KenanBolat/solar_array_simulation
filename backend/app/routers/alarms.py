from fastapi import APIRouter, HTTPException
from ..state import state

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


@router.get("")
def list_alarms(filter: str = "Active"):
    return state.alarms_view(filter)


@router.post("/{alarm_id}/ack")
def ack_alarm(alarm_id: int):
    a = state.ack_alarm(alarm_id)
    if not a:
        raise HTTPException(404, "Unknown alarm")
    return a
