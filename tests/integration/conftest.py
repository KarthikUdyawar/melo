"""
Integration conftest — Postgres-backed db_session and client fixtures.

These fixtures require the Docker Postgres container (via db_engine from
the root conftest). They are ONLY available to tests/integration/.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture()
def db_session(db_engine: Any) -> Generator[Session, None, None]:
    """
    Per-test session on a fresh connection from the Postgres pool.

    - Fresh connection per test (not one shared connection for 90s+).
    - Outer transaction wraps everything; savepoint lets code-under-test
      call session.commit() without actually persisting to the DB.
    - Rollback + connection.close() returns the slot to the pool cleanly.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    session.begin_nested()  # savepoint

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient wired to the rolled-back Postgres session."""
    from app.core.deps import get_db
    from app.main import app

    def _override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
