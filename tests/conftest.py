"""tests/conftest.py
Root conftest — env setup and Docker Postgres lifecycle.

Fixture split
-------------
- This file:   env vars + docker + db_engine (session-scoped, Postgres)
- tests/integration/conftest.py: db_session + client (Postgres-backed)
- tests/unit/conftest.py:        db_session + client (SQLite in-memory, no Docker)

Unit tests NEVER touch Docker. Integration tests get a real Postgres via
pytest-docker with a dynamically allocated host port (no fixed 15432 ->
avoids "port already allocated" when a previous crashed container lingers).
"""

from __future__ import annotations

import os
import socket
import tempfile
import time
from typing import Any

import psycopg2
import pytest

from app.core.db import reset_db

PG_USER = "melo_test"
PG_PASSWORD = "melo_test"
PG_DB = "melo_test"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def pytest_configure(config: object) -> None:
    _tmp = tempfile.mkdtemp()
    os.environ.setdefault("LOG_FILE_PATH", f"{_tmp}/app.log")
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://melo_test:melo_test@localhost:15432/melo_test",
    )


_PG_PORT: int | None = None


def pytest_sessionstart(session: Any) -> None:
    global _PG_PORT
    _PG_PORT = _free_port()
    os.environ["TEST_PG_PORT"] = str(_PG_PORT)


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: Any) -> str:
    return str(pytestconfig.rootdir / "tests" / "docker-compose.test.yml")


@pytest.fixture(scope="session")
def docker_compose_project_name() -> str:
    import uuid

    return f"melo_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def postgres_url(docker_services: Any) -> str:  # type: ignore[misc]
    """Wait for Postgres to be ready, then return its connection URL.
    `docker_services` is provided by pytest-docker.
    """
    port = int(os.environ.get("TEST_PG_PORT", "15432"))
    url = f"postgresql://{PG_USER}:{PG_PASSWORD}@localhost:{port}/{PG_DB}"

    def _check() -> bool:
        try:
            conn = psycopg2.connect(url, connect_timeout=2)
            conn.close()
            return True
        except Exception:
            return False

    # Poll for up to 30 s
    deadline = time.time() + 30
    while time.time() < deadline:
        if _check():
            return url
        time.sleep(0.5)

    raise RuntimeError(f"Postgres on port {port} did not become ready in time")


@pytest.fixture(scope="session")
def db_engine(postgres_url: str) -> Any:
    """Session-scoped SQLAlchemy engine pointing at the test Postgres."""
    # Point settings at test DB before importing anything that calls get_settings()
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["APP_ENV"] = "test"

    # Reset module-level singleton so it picks up the test DATABASE_URL
    import app.core.db as db_module
    import app.models  # noqa: F401 — register all models
    from app.core.db import get_engine

    db_module._engine = None
    db_module._SessionLocal = None

    reset_db()
    engine = get_engine()

    yield engine

    engine.dispose()
