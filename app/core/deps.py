"""FastAPI core dependencies.

Provides database session management and type-annotated dependencies
for use in route handlers.

This module contains the `get_db` dependency and the `DbDep` annotated
type that should be used in route function signatures.
"""

# app/core/deps.py
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session


def get_db() -> Generator[Session, None, None]:
    """Provide a database session per request.

    This is a FastAPI dependency that yields a SQLAlchemy session.
    The session is automatically closed after the request completes.

    Yields:
        Session: SQLAlchemy database session.
    """
    yield from get_session()


# Annotated shorthand for use in route signatures:
#   def route(db: DbDep): ...
DbDep = Annotated[Session, Depends(get_db)]
"""Annotated dependency for database session.

Use this type alias in route handlers for proper type checking and
FastAPI dependency injection.

Example:
    def get_items(db: DbDep) -> list[Item]:
        ...
"""
