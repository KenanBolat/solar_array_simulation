"""Role-based access control.

Roles: observer < operator < supervisor < administrator.
Each route declares the permission it needs. In dev, an X-Dev-User header
selects a seeded user; in production this is replaced by JWT validation.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import User

# permission codes
PERMISSIONS = {
    "view": "View dashboards, measurements, alarms, reports",
    "run_scenario": "Run approved scenarios + routine control",
    "control_output": "Toggle output / set parameters",
    "approve_scenario": "Approve scenarios, change limits, multi-device actions",
    "admin": "Configure devices, users, retention, maintenance console",
}

ROLE_PERMISSIONS = {
    "observer": {"view"},
    "operator": {"view", "run_scenario", "control_output"},
    "supervisor": {"view", "run_scenario", "control_output", "approve_scenario"},
    "administrator": {"view", "run_scenario", "control_output", "approve_scenario", "admin"},
}


@dataclass
class Principal:
    username: str
    role: str
    permissions: set[str]


async def get_current_principal(
    x_dev_user: str | None = Header(default=None, alias="X-Dev-User"),
    session: AsyncSession = Depends(get_session),
) -> Principal:
    username = None
    if settings.dev_auth_enabled and x_dev_user:
        username = x_dev_user
    # default to observer-level seeded user when nothing supplied (dev only)
    if username is None:
        if not settings.dev_auth_enabled:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
        username = "observer"
    row = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if row is None or not row.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown or inactive user")
    role = row.role.name
    return Principal(username=username, role=role, permissions=set(ROLE_PERMISSIONS.get(role, set())))


def require(permission: str):
    async def _dep(principal: Principal = Depends(get_current_principal)) -> Principal:
        if permission not in principal.permissions:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"role '{principal.role}' lacks permission '{permission}'")
        return principal
    return _dep
