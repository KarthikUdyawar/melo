"""
Structured logging configuration for Melo.

``setup_logging()`` is called at MODULE IMPORT TIME (bottom of this file)
so every logger — including those in workers, routers, and services that
import before FastAPI lifespan fires — gets the correct configuration.

Console output:
  development  → colourised ConsoleRenderer (human-readable)
  staging/prod → JSONRenderer (one object per line)

File output (always JSON, production-level):
  Written to LOG_FILE_PATH (default: /var/log/melo/app.log)
  Rotated at 100 MB, 5 backups kept.
"""

import logging
import logging.handlers
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # Import here to avoid circular imports at module load
    from app.core.config import get_settings

    settings = get_settings()

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_env(settings.app_env),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── Console handler ──────────────────────────────────────────────────────
    if settings.is_development:
        console_renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True
        )
    else:
        console_renderer = structlog.processors.JSONRenderer()

    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # Start with just the console handler
    handlers: list[logging.Handler] = [console_handler]

    # ── File handler (Defensive directory creation) ──────────────────────────
    log_file = Path(settings.log_file_path)

    try:
        # Attempt to create the log directory (e.g., /var/log/melo)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=100 * 1024 * 1024,  # 100 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)
        handlers.append(file_handler)

    except (PermissionError, OSError) as e:
        # Fallback for local dev/WSL/CI where /var/log is restricted.
        # We use a simple print here because the logger isn't fully set up yet.
        print(f"--- ⚠️ Logging to file disabled: {e} ---")

    # ── Root logger ──────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(settings.log_level.upper())

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger. Use instead of ``logging.getLogger``."""
    return structlog.get_logger(name)


def _add_env(env: str) -> Callable[..., Any]:
    def processor(
        logger: Any, method: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        event_dict["env"] = env
        return event_dict

    return processor


# ── Configure immediately on import ─────────────────────────────────────────
setup_logging()
