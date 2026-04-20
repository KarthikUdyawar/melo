from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.songs import router as songs_router
from app.core.config import get_settings
from app.core.db import init_db, ping_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    init_db()
    # Future: auto-create MinIO bucket here (WORKER-1)
    _ = settings  # referenced to avoid unused-var lint error
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    return FastAPI(
        title="Melo",
        description="Personal self-hosted audio library",
        version="0.1.0",
        debug=not settings.is_production,
        lifespan=lifespan,
    )


app = create_app()


@app.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    db_ok = ping_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "env": get_settings().app_env,
    }


app.include_router(songs_router)
