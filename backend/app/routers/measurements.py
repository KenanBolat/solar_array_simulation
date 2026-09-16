from fastapi import APIRouter
from ..state import state

router = APIRouter(prefix="/api/measurements", tags=["measurements"])


@router.get("")
def measurements(units: str = "", range: str = "30 min"):
    names = [n for n in units.split(",") if n]
    return state.measurements(names, range)
