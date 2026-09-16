"""Integration test: every command produces an append-only audit record.

Requires PostgreSQL (auto-skipped otherwise). Uses the async session and the
real command service so the full queue -> driver -> persist -> audit path runs.
"""
from __future__ import annotations

import pytest

pytest.importorskip("asyncpg")  # skip module on bare checkouts without DB drivers

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Channel,
    CommandAuditLog,
    CommandRequest,
    CommandResultRow,
    ConnectionProfile,
    Device,
    Mainframe,
    Module,
    Rack,
)
from app.services.command_service import HazardousActionUnconfirmed, run_command  # noqa: E402
from tests.conftest import requires_db  # noqa: E402

pytestmark = requires_db


@pytest.fixture(scope="module", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def _make_device(session, fault: str = "nominal") -> Device:
    rack = Rack(name="IT-Rack")
    session.add(rack)
    await session.flush()
    mf = Mainframe(rack_id=rack.id, name="IT-MF")
    session.add(mf)
    await session.flush()
    mod = Module(mainframe_id=mf.id, slot=1)
    session.add(mod)
    await session.flush()
    ch = Channel(module_id=mod.id, index=1)
    session.add(ch)
    await session.flush()
    prof = ConnectionProfile(name="IT-prof", driver_kind="mock",
                             connection_type="SIM", fault_profile=fault)
    session.add(prof)
    await session.flush()
    dev = Device(name="IT-DEV", rack_id=rack.id, mainframe_id=mf.id, module_id=mod.id,
                 channel_id=ch.id, level="channel", connection_profile_id=prof.id,
                 last_state={})
    session.add(dev)
    await session.flush()
    # reload so the selectin connection_profile is populated for async access
    return (await session.execute(select(Device).where(Device.id == dev.id))).scalar_one()


async def test_idempotent_command_is_audited():
    async with SessionLocal() as session:
        dev = await _make_device(session)
        before = len((await session.execute(select(CommandAuditLog))).scalars().all())

        row = await run_command(session, dev, "read_measurements", {}, actor="operator")
        await session.commit()

        assert row.status == "completed"

        audits = (await session.execute(
            select(CommandAuditLog).where(CommandAuditLog.device_id == dev.id))).scalars().all()
        assert len(audits) == 1
        assert audits[0].actor == "operator"
        assert audits[0].action == "command:read_measurements"
        assert audits[0].outcome == "completed"

        # a request + result row also exist
        reqs = (await session.execute(
            select(CommandRequest).where(CommandRequest.device_id == dev.id))).scalars().all()
        assert len(reqs) == 1
        results = (await session.execute(
            select(CommandResultRow).where(CommandResultRow.request_id == reqs[0].id))).scalars().all()
        assert len(results) == 1

        after = len((await session.execute(select(CommandAuditLog))).scalars().all())
        assert after == before + 1


async def test_hazardous_command_requires_confirmation():
    async with SessionLocal() as session:
        dev = await _make_device(session)
        with pytest.raises(HazardousActionUnconfirmed):
            await run_command(session, dev, "output_on", {}, actor="operator", confirmed=False)


async def test_confirmed_hazardous_command_runs_and_audits():
    async with SessionLocal() as session:
        dev = await _make_device(session)
        row = await run_command(session, dev, "output_on", {}, actor="supervisor",
                                confirmed=True)
        await session.commit()
        assert row.status == "completed"
        assert row.readback_verified is True
        audits = (await session.execute(
            select(CommandAuditLog).where(
                CommandAuditLog.device_id == dev.id,
                CommandAuditLog.template_id == "output_on"))).scalars().all()
        assert len(audits) == 1
        assert audits[0].actor == "supervisor"
