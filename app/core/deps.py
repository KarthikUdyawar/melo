from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_session


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a DB session per request."""
    yield from get_session()


# Annotated shorthand for use in route signatures:
#   def route(db: DbDep): ...
DbDep = Annotated[Session, Depends(get_db)]
