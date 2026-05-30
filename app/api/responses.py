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
