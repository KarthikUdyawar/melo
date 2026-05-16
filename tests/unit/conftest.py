"""
Unit conftest — SQLite in-memory db_session and client, zero Docker.

The tricky part: FastAPI's lifespan calls init_db() which calls get_engine()
which reads DATABASE_URL from settings. If DATABASE_URL still points at
Postgres (set by root conftest pytest_configure), init_db() tries to connect
and blows up.

Fix: patch app.core.db.get_engine at import time so it returns our SQLite
engine, AND set DATABASE_URL to sqlite before importing app.main.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.db import Base


@pytest.fixture(scope="session")
def sqlite_engine():
    """Shared SQLite :memory: engine for the entire unit test session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    """Per-test session wrapped in a transaction that rolls back on teardown."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    session.begin_nested()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session, sqlite_engine) -> Generator[TestClient, None, None]:
    """
    FastAPI TestClient backed by SQLite. No Docker, no Postgres.

    Patches get_engine() so init_db() (called in lifespan) uses our SQLite
    engine instead of trying to connect to Postgres.
    """
    from app.core.deps import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    with (
        patch("app.core.db.get_engine", return_value=sqlite_engine),
        TestClient(app, raise_server_exceptions=True) as c,
    ):
        yield c

    app.dependency_overrides.clear()
