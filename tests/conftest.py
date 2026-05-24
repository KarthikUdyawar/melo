"""tests/conftest.py
Root conftest — env setup and SQLAlchemy engine for integration tests.

Fixture split
-------------
- This file:                     env vars + db_engine (session-scoped, Postgres)
- tests/integration/conftest.py: db_session + client (Postgres-backed)
- tests/unit/conftest.py:        everything SQLite, no Docker, no fixtures here

Integration tests connect to the Postgres container started by:
    docker compose -f tests/docker-compose.test.yml up -d --wait

All connection details are in .env.test (APP_ENV=test), which config.py
loads automatically.  No manual DATABASE_URL wrangling needed here.
"""

from __future__ import annotations

import os
import time

import psycopg2
import pytest

# ── Point the app at .env.test before any app module is imported ───────────────
# Must happen here (pytest_configure), not in pytest_plugin.py, because
# unit/conftest.py also runs early and sets APP_ENV back to "development".
# pytest_configure in the root conftest wins for integration test runs.
os.environ["APP_ENV"] = "test"

PG_URL = "postgresql://melo_test:melo_test@localhost:15432/melo_test"


def pytest_configure(config: object) -> None:
    """Set APP_ENV=test before collection so _env_file() picks .env.test."""
    os.environ["APP_ENV"] = "test"


def _wait_for_postgres(url: str, timeout: int = 30) -> None:
    """Poll until Postgres accepts connections or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(url, connect_timeout=2)
            conn.close()
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(
        f"Postgres did not become ready within {timeout}s.\n"
        "Run: docker compose -f tests/docker-compose.test.yml up -d --wait"
    )


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped SQLAlchemy engine pointing at the test Postgres.

    Only requested by integration tests via db_session in
    tests/integration/conftest.py.  Unit tests never request this fixture
    so no Docker connection is attempted during unit runs.
    """
    import app.core.db as db_module
    import app.models  # noqa: F401 — register all models
    from app.core.config import reset_settings
    from app.core.db import get_engine, reset_db

    # Clear stale settings cache so get_settings() re-reads with APP_ENV=test
    # and picks up .env.test (DATABASE_URL=...port 15432...).
    reset_settings()

    # Reset engine singleton so it rebuilds with the correct URL.
    db_module._engine = None
    db_module._SessionLocal = None

    _wait_for_postgres(PG_URL)

    reset_db()
    engine = get_engine()

    yield engine

    engine.dispose()
