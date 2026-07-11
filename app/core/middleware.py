"""Request logging middleware for Melo.

Emits ``REQUEST_STARTED`` on receipt and ``REQUEST_FINISHED`` on dispatch.

Health endpoint noise suppression:
  ``GET /health`` with status 200 → both events skipped (Grafana probes every 10 s).
  ``GET /health`` with status ≠ 200 → logged normally (infra degraded = signal).
"""

# app/core/middleware.py
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.log_events import LogEvent
from app.core.logging import get_logger

logger = get_logger(__name__)

_HEALTH_PATH = "/health"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one structured line on request receipt and one on response dispatch.

    Suppresses both lines for ``GET /health`` when status is 200 to prevent
    Grafana datasource probes from flooding Loki.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process an HTTP request and emit structured request logs.

        Log request start and completion events, measuring request duration.
        Successful ``GET /health`` requests are excluded to avoid excessive
        monitoring noise, while failed health checks are always logged.
        """
        path = request.url.path
        is_health = path == _HEALTH_PATH

        logger.info(
            LogEvent.REQUEST_STARTED,
            method=request.method,
            path=path,
            query_params=_redacted_query_params(request) or None,
            client_ip=_client_ip(request),
        ) if not is_health else None

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        if is_health and response.status_code == 200:
            return response

        if is_health:
            logger.info(
                LogEvent.REQUEST_STARTED,
                method=request.method,
                path=path,
                query_params=_redacted_query_params(request) or None,
                client_ip=_client_ip(request),
            )

        level = "warning" if response.status_code >= 400 else "info"
        getattr(logger, level)(
            LogEvent.REQUEST_FINISHED,
            method=request.method,
            path=path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        return response


def _client_ip(request: Request) -> str:
    """Return real client IP, preferring ``X-Forwarded-For`` header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _redacted_query_params(request: Request) -> dict[str, str]:
    """Return query params with sensitive values masked."""
    sensitive = {"token", "access_token", "password", "secret", "api_key", "key"}
    return {
        key: ("***" if key.lower() in sensitive else value)
        for key, value in request.query_params.multi_items()
    }
