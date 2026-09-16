import asyncio
import logging

from . import orm, state
from .db import session_scope

POLL_INTERVAL_S = 1.0


async def telemetry_poller():
    """Background task: every second, for every *enabled* unit, records one
    row — a real reading if the unit is online, or an explicit null reading
    (reachable=False) if it isn't. A disabled unit isn't polled at all: it's
    been administratively removed from the fleet, not just unreachable."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            with session_scope() as db:
                units = db.query(orm.Unit).filter(orm.Unit.enabled.is_(True)).all()
                for u in units:
                    v, i, p = state.unit_live_values(u)
                    state.record_measurement(db, u.name, v, i, p, reachable=bool(u.online))
        except Exception:
            # A poll failure shouldn't kill the background loop — log and retry next tick.
            logging.getLogger(__name__).exception("telemetry poll failed")
