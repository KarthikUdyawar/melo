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
from app.core.logging import get_logger
from app.core.middleware import RequestLoggingMiddleware

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
    settings = get_settings()
    init_db()
    logger.info("app_startup", env=settings.app_env, log_file=settings.log_file_path)
    yield
    logger.info("app_shutdown")


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
        # Hide interactive docs in production to reduce attack surface
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(songs_router)
    app.include_router(favorites_router)
    app.include_router(playlists_router)

    return app


app = create_app()


@app.get("/health", tags=["system"], summary="Health check — DB, Redis, MinIO")
async def health() -> JSONResponse:
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
    except Exception:
        return False


def _ping_minio() -> bool:
    """Return True if MinIO bucket is accessible."""
    try:
        from app.services.storage import _client

        s = get_settings()
        _client().bucket_exists(s.minio_bucket)
        return True
    except Exception:
        return False
