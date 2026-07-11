"""Structured logging for Melo — dual renderer.

stdout  → ConsoleRenderer  (human-readable; dev-friendly in docker compose logs)
file    → JSONRenderer      (/var/log/melo/<service>.jsonl; one object per line)

Required fields on every line: timestamp, level, event, service, trace_id.

``configure_logging(service)`` must be called once at startup:
  - FastAPI:  app/main.py  (before lifespan)
  - Celery:   celery_app.py + worker_init signal (after fork)

``setup_logging()`` kept as a compatibility shim — calls configure_logging("api").
"""

# app/core/logging.py
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

_CONFIGURED = False
_SERVICE_NAME = "api"


# ── Public API ────────────────────────────────────────────────────────────────


def configure_logging(
    service: str,
    *,
    log_file: str | None = None,
) -> None:
    """Set up structlog + stdlib logging for ``service``.

    Idempotent — subsequent calls within the same process are no-ops.

    Args:
        service: Service label injected into every log line (``"api"`` or
            ``"worker"``).
        log_file: Path to JSONL file.  When ``None``, resolved from settings.
    """
    global _CONFIGURED, _SERVICE_NAME
    if _CONFIGURED:
        return
    _CONFIGURED = True
    _SERVICE_NAME = service

    resolved_file = log_file or _default_log_file(service)

    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _inject_service(service),
        _inject_trace_id,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,  # ← was True; caching breaks test isolation
    )

    handlers: list[logging.Handler] = [
        _build_console_handler(shared),
    ]

    file_handler = _try_build_file_handler(resolved_file, shared)
    if file_handler is not None:
        handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(logging.DEBUG)

    _silence_noisy_loggers()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger for *name*.

    Args:
        name: Logger name — typically ``__name__``.

    Returns:
        Configured structlog ``BoundLogger``.
    """
    return structlog.get_logger(name)


def setup_logging() -> None:
    """Compatibility shim — delegates to ``configure_logging("api")``."""
    configure_logging("api")


# ── Processors ────────────────────────────────────────────────────────────────


def _inject_service(service: str) -> Callable[..., Any]:
    """Return processor that stamps every record with *service*."""

    def _processor(
        logger: Any,
        method: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict["service"] = service
        return event_dict

    return _processor


def _inject_trace_id(
    logger: Any,
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject active OTEL trace_id, or ``"unknown"`` when no span is active."""
    try:
        from opentelemetry import trace as otel_trace

        span = otel_trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
        else:
            event_dict["trace_id"] = "unknown"
    except Exception:  # noqa: BLE001
        event_dict["trace_id"] = "unknown"

    return event_dict


# ── Handler builders ──────────────────────────────────────────────────────────


def _build_console_handler(
    shared: list[structlog.types.Processor],
) -> logging.StreamHandler:  # type: ignore[type-arg]
    try:
        from app.core.config import get_settings

        is_dev = get_settings().is_development
    except Exception:  # noqa: BLE001
        is_dev = True

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if is_dev
        else structlog.processors.JSONRenderer()
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    return handler


def _try_build_file_handler(
    log_file: str,
    shared: list[structlog.types.Processor],
) -> logging.FileHandler | None:
    path = Path(log_file)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
        handler = logging.FileHandler(str(path), encoding="utf-8")
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)  # ← was INFO; root level already gates this
        return handler
    except Exception as exc:  # noqa: BLE001  ← broaden from PermissionError|OSError
        print(
            f"--- ⚠️  Logging to file disabled ({type(exc).__name__}): {exc} ---",
            file=sys.stderr,
        )
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _default_log_file(service: str) -> str:
    try:
        from app.core.config import get_settings

        base = get_settings().log_file_path
        # Replace "app.log" with "<service>.jsonl" if it's the default name
        p = Path(base)
        return str(p.parent / f"{service}.jsonl")
    except Exception:  # noqa: BLE001
        return f"/var/log/melo/{service}.jsonl"


def _log_level() -> int:
    try:
        from app.core.config import get_settings

        return getattr(logging, get_settings().log_level.upper(), logging.INFO)
    except Exception:  # noqa: BLE001
        return logging.INFO


def _silence_noisy_loggers() -> None:
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)


# NOTE: No auto-configure on import.
# Callers must invoke configure_logging(service) explicitly.
# setup_logging() shim preserved for backward compat — called by celery_app.py
# and main.py before any logger is used.
