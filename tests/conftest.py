"""
Root conftest — shared fixtures for unit and integration tests.

Postgres lifecycle
------------------
`pytest-docker` spins up a real Postgres container once per session.
`db_session` wraps each test in a transaction that is rolled back on teardown,
so tests are fully isolated without truncating tables.

FastAPI TestClient
-----------------
`client` overrides the `get_session` dependency so API tests hit the same
rolled-back transaction as the rest of the test.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Generator
from typing import Any

import psycopg2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import reset_db

# ── Postgres connection details (mirrors docker-compose test service) ─────────
PG_USER = "melo_test"
PG_PASSWORD = "melo_test"
PG_DB = "melo_test"
PG_PORT = 15432  # host port — avoids clashing with dev Postgres on 5432


def pytest_configure(config: object) -> None:
    _tmp = tempfile.mkdtemp()
    os.environ.setdefault("LOG_FILE_PATH", f"{_tmp}/app.log")
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://melo_test:melo_test@localhost:15432/melo_test",
    )


# ── pytest-docker: define which services to spin up ──────────────────────────
@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: Any) -> str:
    return str(pytestconfig.rootdir / "tests" / "docker-compose.test.yml")


@pytest.fixture(scope="session")
def postgres_url(docker_services: Any) -> str:  # type: ignore[misc]
    """
    Wait for Postgres to be ready, then return its connection URL.
    `docker_services` is provided by pytest-docker.
    """
    url = f"postgresql://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"

    def _check() -> bool:
        try:
            conn = psycopg2.connect(url)
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

    raise RuntimeError("Postgres container did not become ready in time")


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
    reset_db()
    engine.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine: Any) -> sessionmaker[Session]:
    return sessionmaker(
        bind=db_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def db_session(
    db_session_factory: sessionmaker[Session],
) -> Generator[Session, None, None]:
    """
    Per-test DB session wrapped in a savepoint.
    All changes are rolled back after each test — no truncation needed.
    """
    connection = db_session_factory.kw["bind"].connect()  # type: ignore[index]
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    # Nested savepoint so rollback works even if the code under test commits
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient with the DB dependency overridden to use the
    rolled-back test session.
    """
    from app.core.deps import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()
