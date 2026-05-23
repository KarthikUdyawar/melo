"""FastAPI response helpers for consistent API envelopes."""

# app/api/responses.py
from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.envelope import Envelope


def envelope_response(
    data: Any,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    """Wrap data in a standard Envelope response."""
    envelope: Envelope[dict[str, object]] = Envelope(
        status_code=status_code,
        message=message,
        body=data,
    )
    return JSONResponse(
        status_code=status_code, content=envelope.model_dump(mode="json")
    )


def paginated_response(
    records: list[Any],
    count: int,
    message: str,
    status_code: int = 200,
    bookmark: Any = None,
) -> JSONResponse:
    """Wrap a page of records in a standard paginated Envelope.

    Args:
        records: Current page of serialized records.
        count: Total matching records (not page size).
        message: Human-readable description.
        status_code: HTTP status code.
        bookmark: Last record's ID for cursor pagination, or None.
    """
    body = {"records": records, "count": count, "bookmark": bookmark}
    envelope: Envelope[dict[str, object]] = Envelope(
        status_code=status_code,
        message=message,
        body=body,
    )
    return JSONResponse(
        status_code=status_code, content=envelope.model_dump(mode="json")
    )
