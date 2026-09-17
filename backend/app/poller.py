import asyncio
import logging

from . import orm, state
from .db import session_scope
from .scpi import Instrument

POLL_INTERVAL_S = 1.0


async def telemetry_poller():
    """Every second, ask each *enabled* unit's instrument for its live state
    (`MEAS:VOLT?`/`FETC:CURR?`/`OUTP?`/`CURR:MODE?`/`STAT:QUES:COND?` in one
    message — see scpi.Instrument.measure) and mirror the answer into the
    unit row plus one measurement row. No valid reply means the unit is
    offline and the sample is an explicit null — never a made-up number.
    Units are polled concurrently so N units cost ~one round trip, not N."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        try:
            with session_scope() as db:
                targets = [(u.name, Instrument.for_unit(u))
                           for u in db.query(orm.Unit).filter(orm.Unit.enabled.is_(True)).all()]
            if not targets:
                continue

            results = await asyncio.gather(*[asyncio.to_thread(inst.measure) for _, inst in targets])

            need_idn = []
            with session_scope() as db:
                for (name, inst), (result, reading) in zip(targets, results):
                    u = db.get(orm.Unit, name)
                    if not u or not u.enabled:
                        continue  # disabled between the poll and now — drop the sample
                    state.apply_reading(db, u, result, reading)
                    if result.ok and not u.firmware:
                        need_idn.append((name, inst))

            if need_idn:  # first contact: learn mainframe model / serial / firmware and the module in this channel
                idns = await asyncio.gather(*[asyncio.to_thread(inst.identify) for _, inst in need_idn])
                with session_scope() as db:
                    for (name, _), res in zip(need_idn, idns):
                        u = db.get(orm.Unit, name)
                        if u and res.ok and res.response:
                            u.firmware = state.describe_identity(res.response)
        except Exception:
            logging.getLogger(__name__).exception("telemetry poll failed")
