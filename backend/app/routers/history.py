from fastapi import APIRouter
from ..state import state

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(filter: str = "All", limit: int = 200):
    return state.history_view(filter, limit)
