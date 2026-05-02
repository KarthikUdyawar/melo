"""
Request logging middleware for Melo.

Logs one structured line on request receipt and one on response dispatch.
Skips verbose logging for ``/health`` (still logs errors there).

Fields logged:
  request  → method, path, query_params, client_ip
  response → status_code, duration_ms
"""

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)

_SKIP_PATHS = frozenset({"/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response: # noqa: ANN001
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
    """Return real client IP, respecting X-Forwarded-For if present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
