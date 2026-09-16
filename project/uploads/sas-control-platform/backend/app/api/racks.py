from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Rack
from app.schemas.common import RackDetailOut, RackOut
from app.security import require

router = APIRouter(prefix="/api/racks", tags=["racks"])


@router.get("", response_model=list[RackOut])
async def list_racks(session: AsyncSession = Depends(get_session),
                     _=Depends(require("view"))):
    rows = (await session.execute(select(Rack).order_by(Rack.position))).scalars().all()
    return rows


@router.get("/{rack_id}", response_model=RackDetailOut)
async def get_rack(rack_id: uuid.UUID, session: AsyncSession = Depends(get_session),
                   _=Depends(require("view"))):
    rack = (await session.execute(select(Rack).where(Rack.id == rack_id))).scalar_one_or_none()
    if not rack:
        raise HTTPException(404, "rack not found")
    return rack
