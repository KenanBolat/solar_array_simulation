"""Integration test: measurement persistence + time-window retrieval.

Requires PostgreSQL (auto-skipped otherwise). Exercises both a direct write
and the telemetry sampler path.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

pytest.importorskip("asyncpg")  # skip module on bare checkouts without DB drivers

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.drivers.base import utcnow  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Channel,
    ConnectionProfile,
    Device,
    Mainframe,
    Measurement,
    Module,
    Rack,
)
from app.services.telemetry import sample_once  # noqa: E402
from tests.conftest import requires_db  # noqa: E402

pytestmark = requires_db


@pytest.fixture(scope="module", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def _make_device(session, fault: str = "nominal", name: str = "MEAS-DEV") -> Device:
    rack = Rack(name="MEAS-Rack")
    session.add(rack)
    await session.flush()
    mf = Mainframe(rack_id=rack.id, name="MEAS-MF")
    session.add(mf)
    await session.flush()
    mod = Module(mainframe_id=mf.id, slot=1)
    session.add(mod)
    await session.flush()
    ch = Channel(module_id=mod.id, index=1)
    session.add(ch)
    await session.flush()
    prof = ConnectionProfile(name="MEAS-prof", driver_kind="mock",
                             connection_type="SIM", fault_profile=fault)
    session.add(prof)
    await session.flush()
    dev = Device(name=name, rack_id=rack.id, mainframe_id=mf.id, module_id=mod.id,
                 channel_id=ch.id, level="channel", connection_profile_id=prof.id,
                 last_state={})
    session.add(dev)
    await session.flush()
    return (await session.execute(select(Device).where(Device.id == dev.id))).scalar_one()


async def test_direct_measurement_roundtrip_and_window():
    async with SessionLocal() as session:
        dev = await _make_device(session, name="MEAS-DIRECT")
        now = utcnow()
        # one old row (outside a 5-minute window) and one fresh row
        session.add(Measurement(
            timestamp_utc=now - timedelta(hours=2), device_id=dev.id, rack_id=dev.rack_id,
            voltage_v=80.0, current_a=7.0, power_w=560.0, output_enabled=True,
            device_state="output_enabled", quality_flag="good"))
        session.add(Measurement(
            timestamp_utc=now, device_id=dev.id, rack_id=dev.rack_id,
            voltage_v=82.0, current_a=7.2, power_w=590.4, output_enabled=True,
            device_state="output_enabled", quality_flag="good"))
        await session.commit()

        window_start = now - timedelta(minutes=5)
        rows = (await session.execute(
            select(Measurement).where(
                Measurement.device_id == dev.id,
                Measurement.timestamp_utc >= window_start,
            ).order_by(Measurement.timestamp_utc))).scalars().all()
        assert len(rows) == 1
        assert rows[0].power_w == pytest.approx(590.4)


async def test_sampler_writes_measurements_for_active_device():
    async with SessionLocal() as session:
        dev = await _make_device(session, name="MEAS-SAMPLED")
        dev_id = dev.id
        await session.commit()

    # run one sampling cycle across all devices in the DB
    await sample_once()

    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Measurement).where(Measurement.device_id == dev_id))).scalars().all()
        assert len(rows) >= 1
        # last_state cache on the device should have been updated too
        dev = (await session.execute(select(Device).where(Device.id == dev_id))).scalar_one()
        assert "device_state" in (dev.last_state or {})
