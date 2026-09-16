from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import state
from ..db import get_db

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(filter: str = "All", limit: int = 200, db: Session = Depends(get_db)):
    return state.history_view(db, filter, limit)
