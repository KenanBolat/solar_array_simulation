"""TimescaleDB policies that must run outside a transaction block.

Continuous aggregates and add_*_policy() calls cannot execute inside a
transaction, so they are applied here over an AUTOCOMMIT connection rather
than in the Alembic migration. Everything is idempotent and safe to re-run.

Called by ``app.seed`` after migrations, and exposed as a console entry too:

    python -m app.timescale
"""
from __future__ import annotations

import logging

import psycopg

from app.config import settings

log = logging.getLogger("sas.timescale")

# 1-minute downsampled rollup used for long-window chart queries. The raw
# hypertable keeps full-resolution data; charts over 1h/24h read the rollup.
_CAGG = """
CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 minute', timestamp_utc) AS bucket,
    device_id,
    avg(voltage_v)  AS voltage_v,
    avg(current_a)  AS current_a,
    avg(power_w)    AS power_w,
    max(power_w)    AS power_w_max,
    min(power_w)    AS power_w_min,
    count(*)        AS samples
FROM measurements
GROUP BY bucket, device_id
WITH NO DATA
"""


def apply_timescale_policies(retention_days: int | None = None) -> None:
    retention_days = retention_days or settings.measurement_retention_days
    statements: list[str] = [
        _CAGG,
        # Keep the rollup fresh.
        "SELECT add_continuous_aggregate_policy('measurements_1m',"
        " start_offset => INTERVAL '3 hours',"
        " end_offset => INTERVAL '1 minute',"
        " schedule_interval => INTERVAL '1 minute',"
        " if_not_exists => TRUE)",
        # Configurable retention on the raw hypertable.
        f"SELECT add_retention_policy('measurements',"
        f" INTERVAL '{int(retention_days)} days', if_not_exists => TRUE)",
    ]
    # AUTOCOMMIT: each policy statement runs in its own implicit transaction.
    with psycopg.connect(_psycopg_dsn(settings.database_url_sync), autocommit=True) as conn:
        for sql in statements:
            try:
                conn.execute(sql)
                log.info("applied timescale policy: %s", sql.split("\n", 1)[0][:60])
            except Exception as exc:  # noqa: BLE001 - log + continue, policies are best-effort
                log.warning("timescale policy skipped (%s): %s", type(exc).__name__, exc)


def _psycopg_dsn(sqlalchemy_url: str) -> str:
    # strip the SQLAlchemy driver prefix -> plain libpq DSN
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    apply_timescale_policies()
