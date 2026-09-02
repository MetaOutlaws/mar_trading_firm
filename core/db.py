"""
Database foundation: engine, session factory, and the declarative base.

SQLAlchemy is used so the local SQLite file can become Postgres by changing
`DATABASE_URL`, with no code changes. SQLite runs in WAL mode because the
trading engine, the agent orchestrator and the API server all read and write
concurrently; without WAL, readers block writers and the API would intermittently
fail while a trade is being recorded.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from config.settings import get_settings

logger = logging.getLogger(__name__)


class UtcDateTime(TypeDecorator):
    """A DateTime that always round-trips as timezone-aware UTC.

    SQLite has no native timezone type, so a `DateTime(timezone=True)` column
    silently returns *naive* datetimes on read. Mixing those with the
    timezone-aware values used everywhere else raises
    "can't subtract offset-naive and offset-aware datetimes" -- and worse, any
    comparison that happens to avoid the exception is wrong by the local UTC
    offset. Normalising here fixes it once for every model rather than at each
    call site.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            # Naive input is treated as UTC rather than local time; guessing
            # local would make stored timestamps machine-dependent.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base shared by trading tables and agent-memory tables.

    One metadata namespace on purpose: a trade and the agent reasoning that led
    to it must be joinable, which is what makes P&L attribution per employee
    possible.
    """


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (once) the configured SQLAlchemy engine."""
    settings = get_settings()
    url = settings.resolved_database_url()
    is_sqlite = url.startswith("sqlite")

    engine = create_engine(
        url,
        echo=False,
        future=True,
        # SQLite defaults to rejecting cross-thread use; the API server and the
        # trading loop legitimately share the engine.
        connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
        pool_pre_ping=True,
    )

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _configure_sqlite(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            # WAL lets readers proceed during writes.
            cursor.execute("PRAGMA journal_mode=WAL")
            # NORMAL is durable enough here and much faster than FULL.
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            # Wait rather than immediately erroring under contention.
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    logger.debug("Database engine ready: %s", url)
    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Cached session factory bound to the configured engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context.

    Commits on success, rolls back on any exception. Every write in the codebase
    goes through this, so a partially-applied trade record is not possible.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create any missing tables.

    Importing the model modules is required for their tables to be registered on
    the shared metadata before `create_all` runs.
    """
    from core.ledger import models as ledger_models  # noqa: F401
    from firm import memory_models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    _migrate_sqlite_columns()
    logger.info("Database schema ready (%d tables).", len(Base.metadata.tables))


def _migrate_sqlite_columns() -> None:
    """create_all does not add columns to existing SQLite tables."""
    from sqlalchemy import inspect, text

    engine = get_engine()
    if engine.dialect.name != "sqlite":
        return
    wanted = {
        "lifecycle": "VARCHAR(16) DEFAULT 'open'",
        "owner_seat": "VARCHAR(48) DEFAULT ''",
        "root_cause": "VARCHAR(128) DEFAULT ''",
        "occurrence_count": "INTEGER DEFAULT 1",
        "last_seen_at": "DATETIME",
        "resolved_at": "DATETIME",
        "timeout_hours": "FLOAT DEFAULT 24.0",
        "severity_promoted": "BOOLEAN DEFAULT 0",
    }
    inspector = inspect(engine)
    if "escalations" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("escalations")}
    with engine.begin() as conn:
        for name, ddl in wanted.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE escalations ADD COLUMN {name} {ddl}"))
                logger.info("Migrated escalations.%s", name)
        # Title used to be VARCHAR(200); widen if SQLite stored it that way.
        try:
            conn.execute(text("UPDATE escalations SET lifecycle = 'open' WHERE lifecycle IS NULL OR lifecycle = ''"))
            conn.execute(
                text(
                    "UPDATE escalations SET lifecycle = 'acknowledged' "
                    "WHERE acknowledged = 1 AND (resolved_at IS NULL) AND lifecycle = 'open'"
                )
            )
        except Exception:
            logger.exception("Could not backfill escalation lifecycle")


def reset_db() -> None:
    """Drop and recreate every table. Destructive; tests and dev resets only."""
    from core.ledger import models as ledger_models  # noqa: F401
    from firm import memory_models  # noqa: F401

    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
    logger.warning("Database reset: all data dropped.")
