"""One serial command queue per physical instrument.

Guarantees that write commands to a single device never run concurrently.
Read/idempotent operations also pass through the same lock to keep ordering
simple and deterministic. Timeouts are enforced per command.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import settings


class InstrumentQueue:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self._lock = asyncio.Lock()
        self.depth = 0

    async def submit(self, coro_factory: Callable[[], Awaitable[Any]],
                     timeout: float | None = None) -> Any:
        timeout = timeout or settings.command_timeout_seconds
        self.depth += 1
        try:
            async with self._lock:  # serialise per instrument
                return await asyncio.wait_for(coro_factory(), timeout=timeout)
        finally:
            self.depth -= 1


class QueueManager:
    def __init__(self):
        self._queues: dict[str, InstrumentQueue] = {}

    def for_device(self, device_id: str) -> InstrumentQueue:
        if device_id not in self._queues:
            self._queues[device_id] = InstrumentQueue(device_id)
        return self._queues[device_id]


_manager: QueueManager | None = None


def get_queue_manager() -> QueueManager:
    global _manager
    if _manager is None:
        _manager = QueueManager()
    return _manager
