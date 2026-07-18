"""Main FastAPI application entry point."""

# app/main.py
import importlib.metadata
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse

from app.api.favorites import router as favorites_router
from app.api.playlists import router as playlists_router
from app.api.responses import envelope_response
from app.api.songs import router as songs_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.tracing import TraceIdMiddleware

configure_logging("api")
logger = get_logger(__name__)

_OPENAPI_TAGS = [
    {"name": "songs", "description": "Submit, list, stream, and delete YouTube audio."},
    {"name": "favorites", "description": "Mark and unmark songs as favorites."},
    {"name": "playlists", "description": "Create and manage ordered playlists."},
    {"name": "system", "description": "Health and operational endpoints."},
]


def _app_version() -> str:
    try:
        return importlib.metadata.version("melo")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    from app.core.log_manager import LogManager
    from app.core.pollers import start_gauge_poller
    from app.core.profiling import configure_pyroscope
    from app.core.tracing import configure_tracing

    settings = get_settings()
    init_db()

    configure_tracing("melo.api")
    configure_pyroscope("melo.api")
    log_manager = LogManager.from_settings("api")
    gauge_scheduler = None
    try:
        gauge_scheduler = start_gauge_poller()

        logger.info(
            "app_startup", env=settings.app_env, log_file=settings.log_file_path
        )
        yield
        logger.info("app_shutdown")

    finally:
        if gauge_scheduler is not None:
            gauge_scheduler.shutdown(wait=False)
        log_manager.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Melo",
        description="Personal self-hosted audio library",
        version=_app_version(),
        debug=not settings.is_production,
        lifespan=lifespan,
        openapi_tags=_OPENAPI_TAGS,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(songs_router)
    app.include_router(favorites_router)
    app.include_router(playlists_router)

    _setup_metrics(app)

    return app


def _setup_metrics(app: FastAPI) -> None:
    """Attach prometheus_fastapi_instrumentator and expose /metrics."""
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


app = create_app()


@app.get("/health", tags=["system"], summary="Health check — DB, Redis, MinIO")
def health() -> JSONResponse:
    """Return liveness status for all infrastructure dependencies."""
    from app.core.db import ping_db

    db_ok = ping_db()
    redis_ok = _ping_redis()
    minio_ok = _ping_minio()

    overall = "ok" if all([db_ok, redis_ok, minio_ok]) else "degraded"

    return envelope_response(
        {
            "status": overall,
            "db": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
            "minio": "up" if minio_ok else "down",
            "env": get_settings().app_env,
        },
        "Health check complete.",
    )


def _ping_redis() -> bool:
    """Return True if Redis responds to PING."""
    try:
        import redis

        s = get_settings()
        r = redis.from_url(s.redis_url, socket_connect_timeout=2)
        r.ping()
        return True
    except Exception:  # noqa: BLE001
        return False


def _ping_minio() -> bool:
    """Return True if MinIO is reachable and the bucket exists."""
    try:
        from app.services.storage import _client

        s = get_settings()
        return bool(_client().bucket_exists(s.minio_bucket))
    except Exception:  # noqa: BLE001
        return False
