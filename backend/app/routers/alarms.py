from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db

router = APIRouter(prefix="/api/alarms", tags=["alarms"])


@router.get("")
def list_alarms(filter: str = "Active", db: Session = Depends(get_db)):
    return state.alarms_view(db, filter)


@router.post("/{alarm_id}/ack")
def ack_alarm(alarm_id: int, db: Session = Depends(get_db)):
    a = state.ack_alarm(db, alarm_id)
    if not a:
        raise HTTPException(404, "Unknown alarm")
    return a
