"""Shared test fixtures.

Unit tests (mock driver, scenario validation) need no database and run
anywhere. The integration tests need a real PostgreSQL + TimescaleDB; they
are skipped automatically when the database in SAS_DATABASE_URL_SYNC is not
reachable, so `pytest` is green both in CI-with-DB and on a bare checkout.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.config import settings


def _postgres_available() -> bool:
    try:
        engine = create_engine(settings.database_url_sync, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL/TimescaleDB not reachable (integration test)",
)
