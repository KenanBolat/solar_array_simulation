from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


@router.get("")
def measurements(units: str = "", range: str = "30 min", db: Session = Depends(get_db)):
    names = [n for n in units.split(",") if n]
    return state.measurements(db, names, range)
