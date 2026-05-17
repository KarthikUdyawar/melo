"""Request logging middleware for Melo.

Logs one structured line on request receipt and one on response dispatch.
Skips verbose logging for ``/health`` (still logs errors there).

Fields logged:
    request  → method, path, query_params, client_ip
    response → status_code, duration_ms
"""
# app/core/middleware.py
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

_SKIP_PATHS = frozenset({"/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs structured request and response information.

    Logs one line when a request is received and one line when the response is
    sent. Skips verbose request/response logging for the ``/health`` endpoint
    (errors are still logged).

    Note:
        This middleware uses structlog-style logging via ``get_logger``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process the request, log it, and log the response.

        Args:
            request: The incoming Starlette request object.
            call_next: The next middleware/handler in the chain to call.

        Returns:
            The response from the downstream handler.
        """
        path = request.url.path
        skip = path in _SKIP_PATHS

        if not skip:
            logger.info(
                "request",
                method=request.method,
                path=path,
                query_params=str(request.query_params) or None,
                client_ip=_client_ip(request),
            )

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if not skip:
            level = "warning" if response.status_code >= 400 else "info"
            getattr(logger, level)(
                "response",
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        return response


def _client_ip(request: Request) -> str:
    """Return the real client IP, preferring X-Forwarded-For header.

    Respects the ``X-Forwarded-For`` header if present (takes the first IP).
    Falls back to ``request.client.host`` or "unknown".

    Args:
        request: The Starlette request object.

    Returns:
        Client IP address as string.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
