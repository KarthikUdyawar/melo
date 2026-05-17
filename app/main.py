"""Main FastAPI application entry point.

This module initializes and configures the Melo application,
including routers, middleware, exception handlers, and lifespan management.
"""

# app/main.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError

from app.api.favorites import router as favorites_router
from app.api.songs import router as songs_router
from app.core.config import get_settings
from app.core.db import init_db, ping_db
from app.core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)

# setup_logging() is called at import time inside app.core.logging —
# importing it here ensures logging is ready before any other module loads.
from app.core.logging import get_logger
from app.core.middleware import RequestLoggingMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Fastapi lifespan context manager.

    Handles application startup and shutdown events.

    On startup:
        - Initializes the database connection pool
        - Logs startup information

    On shutdown:
        - Logs shutdown event

    Args:
        app: The FastAPI application instance.

    Yields:
        None
    """
    settings = get_settings()
    init_db()
    logger.info("app_startup", env=settings.app_env, log_file=settings.log_file_path)
    yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    This is the main factory function that sets up the application with
    title, description, middleware, exception handlers and routers.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()
    app = FastAPI(
        title="Melo",
        description="Personal self-hosted audio library",
        version="0.1.0",
        debug=not settings.is_production,
        lifespan=lifespan,
    )

    app.add_middleware(RequestLoggingMiddleware)

    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(songs_router)
    app.include_router(favorites_router)

    return app


app = create_app()


@app.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    """Health check endpoint.

    Returns basic application and database status information.
    Used by monitoring systems and load balancers.

    Returns:
        dict: Status information containing:
            - status: "ok" or "degraded"
            - db: "up" or "down"
            - env: current environment name
    """
    db_ok = ping_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "env": get_settings().app_env,
    }
