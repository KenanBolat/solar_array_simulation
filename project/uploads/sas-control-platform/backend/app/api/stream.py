"""Server-Sent Events channels for live telemetry, device state, command
status, alarms and scenario progress. SSE chosen over WebSocket for the MVP:
it is one-directional (server->client), proxy-friendly, and trivially
reconnecting. The event-bus interface is transport-agnostic, so swapping in
WebSocket later does not touch producers."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.security import require
from app.services.eventbus import get_event_bus

router = APIRouter(prefix="/api/stream", tags=["stream"])

CHANNELS = {"measurements", "device_state", "command_status", "alarms", "scenario_progress"}


async def _event_source(request: Request, channel: str):
    bus = get_event_bus()
    q = bus.subscribe(channel)
    try:
        yield f"event: connected\ndata: {channel}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(q.get(), timeout=15)
                yield f"event: {channel}\ndata: {data}\n\n"
            except TimeoutError:
                yield ": keepalive\n\n"  # comment line keeps the connection warm
    finally:
        bus.unsubscribe(channel, q)


@router.get("/{channel}")
async def stream(channel: str, request: Request, _=Depends(require("view"))):
    if channel not in CHANNELS:
        from fastapi import HTTPException
        raise HTTPException(404, f"unknown channel; valid: {sorted(CHANNELS)}")
    return StreamingResponse(_event_source(request, channel),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
