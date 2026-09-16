import asyncio

from . import orm, state
from .db import session_scope

POLL_INTERVAL_S = 3.0


async def telemetry_poller():
    """Background task: periodically samples every enabled/online unit and
    persists a real measurement row, the way a real polling worker would."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            with session_scope() as db:
                units = db.query(orm.Unit).filter(orm.Unit.enabled.is_(True), orm.Unit.online.is_(True)).all()
                for u in units:
                    v, i, p = state.unit_live_values(u)
                    state.record_measurement(db, u.name, v, i, p, quality="ok")
        except Exception:
            # A poll failure shouldn't kill the background loop — log and retry next tick.
            import logging
            logging.getLogger(__name__).exception("telemetry poll failed")
