"""tests/unit/conftest.py
Unit conftest — fully self-contained SQLite in-memory stack.

No Docker.  No Postgres.  No network.

Isolation strategy: truncation
-------------------------------
The savepoint-rollback pattern (BEGIN → SAVEPOINT → rollback) breaks when
any code path opens a *second* session via get_session_factory() and calls
commit().  StaticPool reuses one physical connection, so that commit writes
directly to the shared connection, outside the test's outer transaction.
This is exactly what happens when app route handlers call session.commit()
through the get_db override AND any other code (lifespan, health check, etc.)
opens a session via get_session() directly.

The reliable alternative for SQLite + StaticPool:

    1. Each test gets a plain session (no outer transaction tricks).
    2. After each test, DELETE all rows from every table (truncation).
    3. Schema (CREATE TABLE) is created once per session and never dropped
       mid-run — only truncated between tests.

This matches the existing decision log note:
  "SQLite truncation for unit test isolation —
   Savepoint rollback unreliable when endpoint calls db.commit()"
"""

from __future__ import annotations

import os

# ── Step 1: redirect DATABASE_URL to SQLite BEFORE any app import ─────────────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "test"

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import reset_settings  # noqa: E402
from app.core.db import Base  # noqa: E402


@pytest.fixture(scope="session")
def sqlite_engine():
    """Session-scoped SQLite :memory: engine, shared across all unit tests.

    - StaticPool: one physical connection, no pool churn, no file I/O.
    - No isolation_level / BEGIN event hooks needed — we use truncation,
      not savepoints, so we don't need manual transaction control here.
    - Injects itself into app.core.db singletons so init_db(), ping_db(),
      and get_session() all use SQLite, never Postgres.
    """
    import app.core.db as db_module
    import app.models  # noqa: F401 — register all ORM models on Base.metadata

    # ── Step 2: clear stale settings cache ────────────────────────────────────
    reset_settings()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # ── Step 3: inject into app.core.db singletons ────────────────────────────
    # Overriding get_db alone is not enough — init_db(), ping_db(), and any
    # code that calls get_session() directly all read _engine.  Injecting here
    # ensures no code path ever dials out to Postgres.
    db_module._engine = engine
    db_module._SessionLocal = None  # rebuilt on first get_session_factory() call

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    # Restore so a subsequent integration test session starts clean.
    db_module._engine = None
    db_module._SessionLocal = None


def _truncate_all(engine) -> None:
    """Delete every row from every table without dropping schema.

    Tables are deleted in reverse dependency order to satisfy FK constraints
    (SQLite FK enforcement is off by default, but this is correct anyway).
    """
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    """Per-test SQLAlchemy session.

    A plain session — no savepoint tricks.  Isolation is achieved by
    truncating all tables in the autouse `_clean_db` fixture below.
    expire_on_commit=False prevents lazy-load errors after commit, matching
    the production session factory config.
    """
    from app.core.db import get_session_factory

    session: Session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_db(sqlite_engine) -> Generator[None, None, None]:
    """Truncate all tables after every unit test.

    autouse=True means this runs for every test in tests/unit/ automatically.
    Truncating *after* (not before) means a test can inspect state post-run,
    and the very first test always starts with empty tables (create_all gives
    us a clean schema).
    """
    yield
    _truncate_all(sqlite_engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the per-test SQLite session.

    Overrides get_db so every route handler receives db_session.
    The override is removed after each test.
    """
    from app.core.deps import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.pop(get_db, None)
