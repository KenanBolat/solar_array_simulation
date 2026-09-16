from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db

router = APIRouter(prefix="/api", tags=["racks"])


@router.get("/racks")
def list_racks(db: Session = Depends(get_db)):
    return state.racks(db)


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return state.summary(db)
