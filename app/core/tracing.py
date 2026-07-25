"""OTEL tracing setup for Melo.

Responsibilities:
  - configure_tracing(service_name): init SDK + OTLP gRPC exporter → Tempo
  - Auto-instrumentation: FastAPI, SQLAlchemy, HTTPX, Redis
  - get_tracer(name): named tracer for manual spans
  - extract_trace_id(): hex trace ID from active span; "unknown" if none
  - X-Trace-Id middleware: injects trace ID into every response header

Usage::

    # FastAPI startup (main.py lifespan)
    configure_tracing("melo.api")

    # Celery startup (celery_app.py)
    configure_tracing("melo.worker")
"""

# app/core/tracing.py
from __future__ import annotations

import importlib
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_CONFIGURED = False


# ── Public API ────────────────────────────────────────────────────────────────


def configure_tracing(service_name: str, app: FastAPI | None = None) -> None:
    """Initialise OTEL SDK with OTLP gRPC exporter and auto-instrumentation.

    Idempotent — subsequent calls within the same process are no-ops.

    Args:
        service_name: Value for the ``service.name`` resource attribute
            (e.g. ``"melo.api"`` or ``"melo.worker"``).
        app: FastAPI instance to instrument directly via
            ``FastAPIInstrumentor.instrument_app``. Pass when available
            (API service); omit for Celery worker.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    exporter = _build_otlp_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _apply_auto_instrumentation(app)


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider.

    Args:
        name: Tracer name — typically ``__name__``.

    Returns:
        OTEL ``Tracer`` instance.
    """
    return trace.get_tracer(name)


def extract_trace_id() -> str:
    """Return the active span's trace ID as a 32-char hex string.

    Returns:
        Hex trace ID, or ``"unknown"`` when no span is active.
    """
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return "unknown"


# ── Middleware ────────────────────────────────────────────────────────────────


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Inject ``X-Trace-Id`` header into every HTTP response.

    Value is the active OTEL trace ID (32-char hex) or ``"unknown"``.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Process a request and attach the current trace ID to the response.

        Create a server span for the request and add the active OpenTelemetry
        trace ID to the ``X-Trace-Id`` response header.
        """
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=trace.SpanKind.SERVER,
        ):
            trace_id = extract_trace_id()
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_otlp_exporter() -> SpanExporter | None:
    """Build OTLP gRPC exporter; return None if endpoint unreachable or missing."""
    try:
        from app.core.config import get_settings

        settings = get_settings()

        endpoint = getattr(settings, "otlp_endpoint", None)
        if not endpoint:
            endpoint = "http://tempo:4317"

        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True,
        )

    except Exception:  # noqa: BLE001
        logger.warning("otlp_exporter_unavailable", exc_info=True)
        return None


def _apply_auto_instrumentation(app: FastAPI | None = None) -> None:
    """Apply all available OTEL auto-instrumentors. Failures are non-fatal."""
    _try_instrument_fastapi(app)
    _try_instrument(
        "opentelemetry.instrumentation.sqlalchemy", "SQLAlchemyInstrumentor"
    )
    _try_instrument("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor")
    _try_instrument("opentelemetry.instrumentation.redis", "RedisInstrumentor")


def _try_instrument_fastapi(app: FastAPI | None) -> None:
    """Instrument the FastAPI app instance directly, if provided."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
        else:
            FastAPIInstrumentor().instrument()
    except (ImportError, AttributeError) as exc:
        logger.debug("Skipping FastAPI instrumentor: %s", exc)
    except Exception:
        logger.exception("Failed to initialize FastAPI instrumentor")


def _try_instrument(module: str, cls: str) -> None:
    """Attempt to apply an OTEL auto-instrumentor.

    Missing or incompatible instrumentors are ignored.
    """
    try:
        mod = importlib.import_module(module)
        getattr(mod, cls)().instrument()
    except (ImportError, AttributeError) as exc:
        logger.debug(
            "Skipping OpenTelemetry instrumentor %s.%s: %s",
            module,
            cls,
            exc,
        )
    except Exception:
        logger.exception(
            "Failed to initialize OpenTelemetry instrumentor %s.%s",
            module,
            cls,
        )
