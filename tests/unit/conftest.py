"""
Unit conftest — SQLite in-memory with proper nested transaction support.

Uses the recommended pattern (outer transaction + auto-restarting savepoint)
so that:
- Tests can call .commit() freely (as real code does)
- Everything is still rolled back at the end of each test
- No "This transaction is closed" errors
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.db import Base


@pytest.fixture(scope="session")
def sqlite_engine():
    """Shared SQLite :memory: engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite-specific setup for nested transactions / savepoints
    @sa.event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @sa.event.listens_for(engine, "begin")
    def do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    """Per-test session with outer transaction + auto-restarting nested savepoint.

    This is the standard pattern that allows application code to call
    session.commit() while still rolling everything back at test teardown.
    """
    connection = sqlite_engine.connect()
    transaction = connection.begin()

    session = Session(bind=connection, expire_on_commit=False)

    # Start the nested transaction (SAVEPOINT)
    nested = connection.begin_nested()

    # When the app calls session.commit(), it ends the current savepoint.
    # This listener restarts a new one so further operations don't fail.
    @sa.event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    # Teardown: rollback everything
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient using the test database session."""
    from app.core.deps import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
