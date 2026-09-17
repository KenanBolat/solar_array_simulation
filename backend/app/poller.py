import asyncio
import logging

from . import orm, state
from .db import session_scope
from .scpi import Instrument, close_session

POLL_INTERVAL_S = 1.0
BACKOFF_AFTER = 3        # consecutive failures before slowing down
BACKOFF_EVERY = 5        # ...then try only every Nth second

_failures: dict[str, int] = {}
_tick = 0


def reset_backoff():
    _failures.clear()


def _due(name: str) -> bool:
    """Don't hammer an instrument that isn't answering: after a few failures
    retry every 5 s instead of every second, so the app itself never becomes
    the client that keeps its connection slots busy."""
    return _failures.get(name, 0) < BACKOFF_AFTER or _tick % BACKOFF_EVERY == 0


def measure_unit(ip: str, port: int, transport: str, channel: int):
    """Poll one unit. Returns (result, reading, resolved_transport). With
    transport 'auto' the documented VXI-11 path is tried first, then the raw
    socket; the one that answers is reported so the unit can be pinned to it."""
    if transport != "auto":
        result, reading = Instrument(ip, port, transport, channel).measure()
        return result, reading, None
    result = reading = None
    for t in ("vxi11", "socket"):
        inst = Instrument(ip, port, t, channel)
        result, reading = inst.measure()
        if result.ok:
            return result, reading, t
        close_session(inst.address)
    return result, reading, None


def _pin_transport(db, u: orm.Unit, transport: str | None):
    if transport and u.transport == "auto":
        u.transport = transport
        u.visa = state.derive_visa(u.ip_address, u.scpi_port, transport)
        db.commit()


async def telemetry_poller():
    """Every second, ask each *enabled* unit's instrument for its live state
    (`MEAS:VOLT?`/`FETC:CURR?`/`OUTP?`/`CURR:MODE?`/`STAT:QUES:COND?` in one
    message — see scpi.Instrument.measure) and mirror the answer into the
    unit row plus one measurement row. No valid reply means the unit is
    offline and the sample is an explicit null — never a made-up number.
    Units are polled concurrently so N units cost ~one round trip, not N."""
    global _tick
    while True:
        await asyncio.sleep(POLL_INTERVAL_S)
        _tick += 1
        try:
            with session_scope() as db:
                targets = [(u.name, u.ip_address, u.scpi_port, u.transport, u.channel)
                           for u in db.query(orm.Unit).filter(orm.Unit.enabled.is_(True)).all()
                           if _due(u.name)]
            if not targets:
                continue

            results = await asyncio.gather(
                *[asyncio.to_thread(measure_unit, ip, port, tr, ch) for _, ip, port, tr, ch in targets]
            )

            need_idn = []
            with session_scope() as db:
                for (name, *_), (result, reading, resolved) in zip(targets, results):
                    u = db.get(orm.Unit, name)
                    if not u or not u.enabled:
                        continue  # disabled between the poll and now — drop the sample
                    _pin_transport(db, u, resolved)
                    state.apply_reading(db, u, result, reading)
                    _failures[name] = 0 if result.ok else _failures.get(name, 0) + 1
                    if result.ok and not u.firmware:
                        need_idn.append((name, Instrument.for_unit(u)))

            if need_idn:  # first contact: learn mainframe model / serial / firmware and the module in this channel
                idns = await asyncio.gather(*[asyncio.to_thread(inst.identify) for _, inst in need_idn])
                with session_scope() as db:
                    for (name, _), res in zip(need_idn, idns):
                        u = db.get(orm.Unit, name)
                        if u and res.ok and res.response:
                            u.firmware = state.describe_identity(res.response)
        except Exception:
            logging.getLogger(__name__).exception("telemetry poll failed")
