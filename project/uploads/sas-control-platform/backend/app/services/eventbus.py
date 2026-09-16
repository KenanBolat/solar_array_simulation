"""In-process async pub/sub for SSE fan-out.

Channels: device_state, measurements, command_status, alarms, scenario_progress.
Redis can be layered behind this later for multi-process fan-out; the
interface stays identical.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


class EventBus:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs[channel].add(q)
        return q

    def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        self._subs[channel].discard(q)

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str)
        for q in list(self._subs[channel]):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass  # drop for slow consumers


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
