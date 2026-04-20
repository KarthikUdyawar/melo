# app/core/config.py
import os
from functools import lru_cache

from dotenv import dotenv_values
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid environments
APP_ENVS = {"development", "staging", "production"}


def _env_file() -> str:
    """
    Resolve which .env file to load.

    Priority:
      1. APP_ENV from the real OS environment (not yet parsed by pydantic).
      2. Falls back to "development".

    Returns the path: .env.development / .env.staging / .env.production
    """
    app_env = os.environ.get("APP_ENV", "development").lower()
    if app_env not in APP_ENVS:
        raise ValueError(
            f"APP_ENV={app_env!r} is not valid. Choose from: {sorted(APP_ENVS)}"
        )
    return f".env.{app_env}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        env_prefix="",  # optional
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    log_level: str = Field(default="info")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql://melo:melo@localhost:5432/melo",
    )

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker: str = Field(default="redis://localhost:6379/0")
    celery_backend: str = Field(default="redis://localhost:6379/1")

    # ── MinIO ─────────────────────────────────────────────────────────────────
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="songs")
    minio_secure: bool = Field(default=False)
    minio_public_url: str | None = Field(default=None)

    # ── Derived ───────────────────────────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_staging(self) -> bool:
        return self.app_env == "staging"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @model_validator(mode="after")
    def _validate_minio_secure_in_prod(self) -> "Settings":
        if self.is_production and not self.minio_secure:
            import warnings

            warnings.warn(
                "MINIO_SECURE=false in production is insecure.",
                stacklevel=2,
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def force_env_file_priority(cls, values):
        env_values = dotenv_values(_env_file())

        # normalize keys to lowercase
        normalized = {k.lower(): v for k, v in env_values.items() if v is not None}

        # merge: env overrides everything
        return {**values, **normalized}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    """
    Clear the cached Settings instance.

    Use in tests when you need to swap APP_ENV or override env vars:

        monkeypatch.setenv("APP_ENV", "production")
        reset_settings()
        s = get_settings()   # re-reads .env.production
    """
    get_settings.cache_clear()
