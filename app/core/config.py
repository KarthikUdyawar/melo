"""Application settings and configuration.

This module defines the centralized settings management using Pydantic Settings.
It automatically loads environment-specific `.env.{development|staging|production}`
files and provides type-safe, validated configuration for the entire application.
"""
# app/core/config.py
import os
from functools import lru_cache
from typing import Any

from dotenv import dotenv_values
from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valid environments
APP_ENVS = {"development", "staging", "production", "test"}


def _env_file() -> str:
    """Determine which .env file should be loaded based on APP_ENV.

    Priority:
        1. `APP_ENV` environment variable (real OS env).
        2. Falls back to "development".

    Returns:
        Path to the environment file (e.g. `.env.development`, `.env.staging`).

    Raises:
        ValueError: If APP_ENV is set to an invalid value.
    """
    app_env = os.environ.get("APP_ENV", "development").lower()
    if app_env not in APP_ENVS:
        raise ValueError(
            f"APP_ENV={app_env!r} is not valid. Choose from: {sorted(APP_ENVS)}",
        )
    return f".env.{app_env}"


class Settings(BaseSettings):
    """Main application settings using Pydantic.

    Loads configuration from environment variables and `.env.*` files with
    proper priority and validation. Provides computed environment flags
    and runtime checks.
    """
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
    log_file_path: str = Field(default="/var/log/melo/app.log")

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
        """Return True if the current environment is production."""
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_staging(self) -> bool:
        """Return True if the current environment is staging."""
        return self.app_env == "staging"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_development(self) -> bool:
        """Return True if the current environment is development."""
        return self.app_env == "development"

    @model_validator(mode="after")
    def _validate_minio_secure_in_prod(self) -> "Settings":
        """Validate that MinIO is using secure connection in production.

        Warns if `MINIO_SECURE=false` is used in production environment.
        """
        if self.is_production and not self.minio_secure:
            import warnings

            warnings.warn(
                "MINIO_SECURE=false in production is insecure.",
                stacklevel=2,
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def force_env_file_priority(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Force values from the selected .env file to have highest priority.

        This validator runs before normal field validation to ensure that
        settings from `.env.{env}` override both defaults and any passed values.

        Note:
            This is a classmethod that receives raw input values.
        """
        env_values = dotenv_values(_env_file())

        # normalize keys to lowercase
        normalized = {k.lower(): v for k, v in env_values.items() if v is not None}

        # merge: env overrides everything
        return {**values, **normalized}


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance.

    The settings are parsed only once per process thanks to `lru_cache`.

    Returns:
        Settings: The application settings object.
    """
    return Settings()


def reset_settings() -> None:
    """Clear the cached Settings instance.

    Useful in tests when you need to change `APP_ENV` or other environment
    variables after the settings have already been loaded.

    Example:
        monkeypatch.setenv("APP_ENV", "production")
        reset_settings()
        settings = get_settings()  # will reload with new environment
    """
    get_settings.cache_clear()
