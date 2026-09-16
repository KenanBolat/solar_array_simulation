from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk


class Rack(UUIDPk, Timestamps, Base):
    __tablename__ = "racks"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str] = mapped_column(String(128), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    mainframes: Mapped[list[Mainframe]] = relationship(
        back_populates="rack", lazy="selectin")


class Mainframe(UUIDPk, Timestamps, Base):
    __tablename__ = "mainframes"
    rack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("racks.id"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), default="generic-mainframe")
    rack: Mapped[Rack] = relationship(back_populates="mainframes", lazy="selectin")
    modules: Mapped[list[Module]] = relationship(
        back_populates="mainframe", lazy="selectin")


class Module(UUIDPk, Timestamps, Base):
    __tablename__ = "modules"
    mainframe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mainframes.id"))
    slot: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(64), default="")
    mainframe: Mapped[Mainframe] = relationship(back_populates="modules", lazy="selectin")
    channels: Mapped[list[Channel]] = relationship(
        back_populates="module", lazy="selectin")


class Channel(UUIDPk, Timestamps, Base):
    __tablename__ = "channels"
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id"))
    index: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(64), default="")
    module: Mapped[Module] = relationship(back_populates="channels", lazy="selectin")


class ConnectionProfile(UUIDPk, Timestamps, Base):
    __tablename__ = "device_connection_profiles"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    driver_kind: Mapped[str] = mapped_column(String(16), default="mock")  # mock | e4360
    connection_type: Mapped[str] = mapped_column(String(16), default="SIM")  # SIM|LAN|USB|GPIB
    visa_resource: Mapped[str] = mapped_column(String(128), default="")
    fault_profile: Mapped[str] = mapped_column(String(16), default="nominal")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Device(UUIDPk, Timestamps, Base):
    """A logical controlled unit. May map to a mainframe, module, or channel."""
    __tablename__ = "devices"
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("racks.id"))
    mainframe_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mainframes.id"), nullable=True)
    module_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("modules.id"), nullable=True)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="channel")  # mainframe|module|channel
    connection_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("device_connection_profiles.id"))
    connection_profile: Mapped[ConnectionProfile] = relationship(lazy="selectin")
    # last-known cached state (authoritative live state comes from the driver)
    last_state: Mapped[dict] = mapped_column(JSON, default=dict)


class DeviceCapability(UUIDPk, Timestamps, Base):
    __tablename__ = "device_capabilities"
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("devices.id"))
    capability_map_version: Mapped[str] = mapped_column(String(16), default="0.1.0")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
