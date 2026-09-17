from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DB_PATH = Path(__file__).resolve().parent.parent / "data.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def ensure_columns(base):
    """Minimal forward migration: add any ORM column missing from an existing
    SQLite table (ALTER TABLE ... ADD COLUMN), so a schema change no longer
    means deleting data.db — and with it the units you've addressed at real
    instruments. Column removals/renames are not handled."""
    insp = inspect(engine)
    with engine.begin() as conn:
        for table in base.metadata.sorted_tables:
            if table.name not in insp.get_table_names():
                continue
            existing = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(engine.dialect)}'
                default = col.default.arg if col.default is not None and not callable(col.default.arg) else None
                if default is not None:
                    ddl += " DEFAULT " + (f"'{default}'" if isinstance(default, str) else str(int(default) if isinstance(default, bool) else default))
                elif not col.nullable:
                    ddl += " DEFAULT ''" if "CHAR" in str(col.type).upper() or "TEXT" in str(col.type).upper() else " DEFAULT 0"
                conn.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """For use outside FastAPI's request/dependency cycle (e.g. the telemetry poller)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
