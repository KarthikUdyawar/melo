"""FastAPI exception handlers for standardized error responses.

This module contains custom exception handlers that convert various exceptions
into a consistent Envelope response format using the standardized error
envelope structure.
"""
# app/core/exception_handlers.py
from fastapi import Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.envelope import Envelope


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException and return a standardized error response.

    Args:
        request: The FastAPI request object.
        exc: The HTTPException that was raised.

    Returns:
        JSONResponse containing the error details wrapped in an Envelope.
    """
    envelope: Envelope[None] = Envelope(
        status_code=exc.status_code,
        message=str(exc.detail),
        body=None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope.model_dump(mode="json"),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Handle RequestValidationError and return a standardized error response.

    Args:
        request: The FastAPI request object.
        exc: The RequestValidationError containing validation errors.

    Returns:
        JSONResponse with status 422 and validation errors formatted in
        the Envelope structure.
    """
    errors = exc.errors()
    message = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors
    )
    envelope: Envelope[None] = Envelope(status_code=422, message=message, body=None)
    return JSONResponse(
        status_code=422,
        content=envelope.model_dump(mode="json"),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle any uncaught exception and return a generic server error response.

    Args:
        request: The FastAPI request object.
        exc: The unhandled exception.

    Returns:
        JSONResponse with status 500 and a generic error message in
        Envelope format.
    """
    envelope: Envelope[None] = Envelope(
        status_code=500,
        message="Internal server error.",
        body=None,
    )
    return JSONResponse(
        status_code=500,
        content=envelope.model_dump(mode="json"),
    )
