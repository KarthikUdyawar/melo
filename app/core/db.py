# app/core/db.py
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""


# Lazy singletons — built on first access so tests can set env vars first.
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
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
    """Yield a SQLAlchemy session and close it when done."""
    session: Session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """
    Create all tables that are registered on Base.metadata.

    Called once at application startup (e.g. in the FastAPI lifespan handler).
    Safe to call multiple times — CREATE TABLE IF NOT EXISTS semantics via
    SQLAlchemy's checkfirst=True default.

    Models must be imported before this is called so SQLAlchemy knows about
    them. Import them explicitly in the lifespan or in app/models/__init__.py.
    """
    import app.models  # noqa: F401 — ensure all models are registered

    Base.metadata.create_all(bind=get_engine(), checkfirst=True)


def reset_db() -> None:
    """
    Drop and recreate all tables. **Test-only** — never call in production.

    Typical usage in conftest.py:

        @pytest.fixture(autouse=True)
        def fresh_db():
            reset_db()
            yield
    """
    global _engine, _SessionLocal
    import app.models  # noqa: F401

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine, checkfirst=True)

    # Flush session factory so next get_session() uses fresh tables
    _SessionLocal = None


def ping_db() -> bool:
    """Return True if the database is reachable."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
