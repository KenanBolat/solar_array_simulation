from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk

role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", PG_UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", PG_UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True),
)


class Permission(UUIDPk, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")


class Role(UUIDPk, Timestamps, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, lazy="selectin")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    role: Mapped[Role] = relationship(lazy="selectin")
