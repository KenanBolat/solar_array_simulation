from fastapi import APIRouter
from ..state import state

router = APIRouter(prefix="/api", tags=["racks"])


@router.get("/racks")
def list_racks():
    return state.racks()


@router.get("/summary")
def summary():
    return state.summary()
