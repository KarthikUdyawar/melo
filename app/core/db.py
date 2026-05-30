"""Database configuration and session management for SQLAlchemy.

This module provides lazy-initialized engine and session factory singletons,
dependency injection helpers for FastAPI, and utility functions for database
initialization and health checks.
"""

# app/core/db.py
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models in the application."""


# Lazy singletons — built on first access so tests can set env vars first.
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the SQLAlchemy Engine instance (lazy singleton).

    The engine is created on first access using the database URL from
    application settings. Subsequent calls return the cached instance.

    Returns:
        SQLAlchemy Engine connected to the configured database.
    """
    global _engine
    if _engine is None:
        from app.core.config import get_settings

        settings = get_settings()
        connect_args: dict[str, object] = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> "sessionmaker[Session]":
    """Return the SQLAlchemy sessionmaker (lazy singleton).

    The session factory is created on first access and bound to the engine
    returned by ``get_engine()``.

    Returns:
        Configured sessionmaker instance.
    """
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """Provide a SQLAlchemy session for FastAPI dependency injection.

    Yields a session and ensures it is closed after the request is completed.

    Yields:
        Active SQLAlchemy Session.
    """
    session: Session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def _create_pg_extensions(engine: Engine) -> None:
    """Create required PostgreSQL extensions if running against Postgres.

    pg_trgm is needed for the GIN trigram index on songs.title, which
    supports leading-and-trailing ILIKE '%search%' queries.  The statement
    is idempotent (IF NOT EXISTS) and skipped entirely on SQLite so unit
    tests are unaffected.

    Args:
        engine: Active SQLAlchemy Engine to execute against.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()


def init_db() -> None:
    """Create all tables defined by models inheriting from Base.

    Should be called once during application startup (typically in the
    FastAPI lifespan handler). Safe to call multiple times due to
    ``checkfirst=True``.

    Note:
        All models must be imported before calling this function so that
        SQLAlchemy registers them on ``Base.metadata``.
    """
    import app.models  # noqa: F401 — ensure all models are registered

    engine = get_engine()
    _create_pg_extensions(engine)
    Base.metadata.create_all(bind=engine, checkfirst=True)


def reset_db() -> None:
    """Drop and recreate all tables.

    **For testing purposes only.** Never use in production.

    This is typically used in pytest fixtures to ensure a clean database
    state before each test.
    """
    global _engine, _SessionLocal
    import app.models  # noqa: F401

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    _create_pg_extensions(engine)
    Base.metadata.create_all(bind=engine, checkfirst=True)

    # Flush session factory so next get_session() uses fresh tables
    _SessionLocal = None


def ping_db() -> bool:
    """Check if the database is reachable.

    Returns:
        True if the database responds to a simple query, False otherwise.
    """
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
