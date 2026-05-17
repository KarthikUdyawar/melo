"""FastAPI response helpers for consistent API envelopes.

This module provides utility functions to wrap responses in a standard
Envelope format for consistent API responses across the application.
"""
# app/api/responses.py
from typing import Any

from fastapi.responses import JSONResponse

from app.schemas.envelope import Envelope


def envelope_response(
    data: Any,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    """Create a standardized enveloped JSON response.

    Args:
        data: The main payload/data to be returned in the response body.
        message: Human-readable message describing the response.
        status_code: HTTP status code for the response. Defaults to 200.

    Returns:
        JSONResponse with the data wrapped in an Envelope schema.
    """
    envelope: Envelope[dict[str, object]] = Envelope(
        status_code=status_code, message=message, body=data,
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )


def paginated_response(
    records: list[Any],
    count: int,
    message: str,
    status_code: int = 200,
) -> JSONResponse:
    """Create a standardized paginated enveloped JSON response.

    Args:
        records: List of records/items for the current page.
        count: Total number of records available (used for pagination metadata).
        message: Human-readable message describing the response.
        status_code: HTTP status code for the response. Defaults to 200.

    Returns:
        JSONResponse containing the paginated records wrapped in an Envelope.
    """
    body = {"records": records, "count": count}
    envelope: Envelope[dict[str, object]] = Envelope(
        status_code=status_code, message=message, body=body,
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )
