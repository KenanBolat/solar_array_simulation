"""Standalone instrument worker.

Runs the telemetry sampling loop in its own process (separate from the API).
In a real deployment this process owns the serial command queues and the
VISA sessions; in SIMULATION MODE it drives the MockE4360Driver instances.

The API can also run an in-process sampler in development (see app.main), but
the dedicated worker is the production-shaped path and is what docker-compose
launches as the ``worker`` service.

Run with:  python -m worker.telemetry_worker
"""
from __future__ import annotations

import asyncio
import signal

from app.config import settings
from app.logging import configure_logging, get_logger
from app.services.telemetry import telemetry_loop

log = get_logger("worker")


async def _main() -> None:
    stop = asyncio.Event()

    def _handle(*_):
        log.info("shutdown signal received; stopping telemetry loop")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle)
        except NotImplementedError:  # pragma: no cover (Windows)
            signal.signal(sig, lambda *_: _handle())

    mode = "HARDWARE ENABLED" if settings.hardware_enabled else "SIMULATION MODE"
    log.info("instrument worker started (%s), interval=%.2fs",
             mode, settings.telemetry_interval_seconds)
    await telemetry_loop(stop)
    log.info("instrument worker stopped cleanly")


def main() -> None:
    configure_logging()
    asyncio.run(_main())


if __name__ == "__main__":
    main()
