"""Tests for health log suppression in RequestLoggingMiddleware."""

# tests/unit/test_middleware_health.py
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.core.log_events import LogEvent


def _make_request(path: str, method: str = "GET") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
    }
    return Request(scope)


async def _next_200(request: Request) -> Response:
    return Response("ok", status_code=200)


async def _next_500(request: Request) -> Response:
    return Response("fail", status_code=500)


@pytest.mark.anyio
async def test_health_200_suppresses_request_log():
    """GET /health with 200 must NOT log REQUEST_STARTED."""
    from app.core.middleware import RequestLoggingMiddleware

    middleware = RequestLoggingMiddleware(app=MagicMock())
    request = _make_request("/health")

    logged_events: list[str] = []

    def capture(event: str, **kwargs: object) -> None:
        logged_events.append(event)

    with patch("app.core.middleware.logger") as mock_logger:
        mock_logger.info.side_effect = capture
        mock_logger.warning.side_effect = lambda e, **kw: logged_events.append(e)
        await middleware.dispatch(request, _next_200)

    assert LogEvent.REQUEST_STARTED not in logged_events
    assert LogEvent.REQUEST_FINISHED not in logged_events


@pytest.mark.anyio
async def test_health_500_logs_request():
    """GET /health with 500 MUST log REQUEST_STARTED (infra degraded signal)."""
    from app.core.middleware import RequestLoggingMiddleware

    middleware = RequestLoggingMiddleware(app=MagicMock())
    request = _make_request("/health")

    logged_events: list[str] = []

    def capture_info(event: str, **kwargs: object) -> None:
        logged_events.append(str(event))

    def capture_warn(event: str, **kwargs: object) -> None:
        logged_events.append(str(event))

    with patch("app.core.middleware.logger") as mock_logger:
        mock_logger.info.side_effect = capture_info
        mock_logger.warning.side_effect = capture_warn
        await middleware.dispatch(request, _next_500)

    assert any(
        LogEvent.REQUEST_STARTED in e or e == LogEvent.REQUEST_STARTED
        for e in logged_events
    )


@pytest.mark.anyio
async def test_non_health_path_logs_request():
    """Non-health paths always log REQUEST_STARTED."""
    from app.core.middleware import RequestLoggingMiddleware

    middleware = RequestLoggingMiddleware(app=MagicMock())
    request = _make_request("/songs")

    logged_events: list[str] = []

    with patch("app.core.middleware.logger") as mock_logger:
        mock_logger.info.side_effect = lambda e, **kw: logged_events.append(str(e))
        mock_logger.warning.side_effect = lambda e, **kw: logged_events.append(str(e))
        await middleware.dispatch(request, _next_200)

    assert any(
        LogEvent.REQUEST_STARTED in e or e == str(LogEvent.REQUEST_STARTED)
        for e in logged_events
    )
