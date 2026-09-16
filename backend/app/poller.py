import asyncio
import logging

from . import orm, state
from .db import session_scope
from .driver import check_reachable

POLL_INTERVAL_S = 1.0


async def telemetry_poller():
    """Every second: real TCP-reachability probe against every *enabled*
    unit's IP:port (concurrently, so N units cost ~one timeout, not N), then
    one measurement row per unit — a real reading if reachable, an explicit
    null if not. A disabled unit isn't probed or polled at all."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            with session_scope() as db:
                targets = [(u.name, u.ip_address, u.scpi_port)
                           for u in db.query(orm.Unit).filter(orm.Unit.enabled.is_(True)).all()]

            if not targets:
                continue

            results = await asyncio.gather(
                *[asyncio.to_thread(check_reachable, ip, port) for _, ip, port in targets]
            )

            with session_scope() as db:
                for (name, _, _), reachable in zip(targets, results):
                    u = db.get(orm.Unit, name)
                    if not u or not u.enabled:
                        continue  # disabled between the probe and now — drop the sample
                    u.online = reachable
                    v, i, p = state.unit_live_values(u)
                    state.record_measurement(db, u.name, v, i, p, reachable=reachable)
        except Exception:
            # A poll failure shouldn't kill the background loop — log and retry next tick.
            logging.getLogger(__name__).exception("telemetry poll failed")
