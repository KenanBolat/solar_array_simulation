"""initial schema + TimescaleDB hypertable for measurements

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-23

Strategy
--------
The relational schema is created directly from the SQLAlchemy model
metadata so the migration can never drift from the ORM definitions. The
TimescaleDB-specific objects (extension + hypertable) are then applied with
raw DDL.

Continuous aggregates and retention/compression *policies* require an
autocommit connection (they cannot run inside a transaction block), so they
are applied separately by ``app.timescale.apply_timescale_policies`` which the
seed/bootstrap step invokes. The hypertable itself is created here because
``create_hypertable`` is transaction-safe.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.models import Base

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # TimescaleDB ships preinstalled on the timescaledb image. The extension
    # call is idempotent; on a plain PostgreSQL image it will raise, which is
    # a clear signal the wrong image is in use.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # Create every table defined on the ORM metadata in dependency order.
    Base.metadata.create_all(bind=bind)

    # Promote measurements to a hypertable partitioned on timestamp_utc.
    # The composite PK (timestamp_utc, device_id) already includes the
    # partitioning column, satisfying TimescaleDB's uniqueness requirement.
    op.execute(
        "SELECT create_hypertable("
        "  'measurements', 'timestamp_utc',"
        "  chunk_time_interval => INTERVAL '1 day',"
        "  if_not_exists => TRUE,"
        "  migrate_data => TRUE)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    # Drop in reverse dependency order via metadata.
    Base.metadata.drop_all(bind=bind)
