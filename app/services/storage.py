"""MinIO storage service for file upload and presigned URL generation."""

# app/services/storage.py
import time
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.log_events import LogEvent
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageError(Exception):
    """Exception raised when a MinIO operation fails."""


def _client() -> Minio:
    """Return a configured MinIO client instance."""
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


def ensure_bucket_exists() -> None:
    """Create the configured bucket if it does not already exist."""
    s = get_settings()
    client = _client()

    logger.info(
        LogEvent.MINIO_BUCKET_STARTED,
        phase="ensure_bucket",
        bucket=s.minio_bucket,
        endpoint=s.minio_endpoint,
    )

    try:
        exists = client.bucket_exists(s.minio_bucket)
        if not exists:
            client.make_bucket(s.minio_bucket)
            logger.info(
                LogEvent.MINIO_BUCKET_DONE,
                phase="bucket_created",
                bucket=s.minio_bucket,
            )
        else:
            logger.info(
                LogEvent.MINIO_BUCKET_DONE,
                phase="bucket_exists",
                bucket=s.minio_bucket,
            )
    except S3Error as exc:
        logger.error(
            LogEvent.MINIO_BUCKET_FAILED,
            phase="ensure_bucket",
            bucket=s.minio_bucket,
            error=str(exc),
        )
        raise StorageError(
            f"Could not ensure bucket {s.minio_bucket!r}: {exc}"
        ) from exc


def upload_file(local_path: Path, object_key: str) -> str:
    """Upload a local file to MinIO at the given object key."""
    from app.core.metrics import minio_upload_duration_seconds
    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("minio.upload"):
        s = get_settings()
        client = _client()

        if not local_path.exists():
            logger.error(
                LogEvent.MINIO_UPLOAD_FAILED,
                path=str(local_path),
                key=object_key,
                reason="file_missing",
            )
            raise StorageError(f"File does not exist: {local_path}")

        file_size = local_path.stat().st_size

        logger.info(
            LogEvent.MINIO_UPLOAD_STARTED,
            path=str(local_path),
            size=file_size,
            bucket=s.minio_bucket,
            key=object_key,
        )

        t0 = time.monotonic()
        try:
            client.fput_object(
                bucket_name=s.minio_bucket,
                object_name=object_key,
                file_path=str(local_path),
                content_type="audio/mpeg",
            )
            minio_upload_duration_seconds.observe(time.monotonic() - t0)
            logger.info(
                LogEvent.MINIO_UPLOAD_DONE,
                path=str(local_path),
                size=file_size,
                bucket=s.minio_bucket,
                key=object_key,
            )
        except S3Error as exc:
            logger.error(
                LogEvent.MINIO_UPLOAD_FAILED,
                path=str(local_path),
                bucket=s.minio_bucket,
                key=object_key,
                error=str(exc),
            )
            raise StorageError(
                f"Upload failed for {local_path!r} → {object_key!r}: {exc}"
            ) from exc
        except Exception:
            logger.exception(
                LogEvent.MINIO_UPLOAD_FAILED,
                path=str(local_path),
                bucket=s.minio_bucket,
                key=object_key,
            )
            raise

        return object_key


def get_presigned_url(object_key: str, expires_seconds: int = 3600) -> str:
    """Generate a presigned GET URL for an object in MinIO."""
    from datetime import timedelta
    from urllib.parse import urlparse, urlunparse

    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("minio.stream"):
        s = get_settings()
        client = _client()

        logger.debug(
            LogEvent.MINIO_STREAM_STARTED,
            key=object_key,
            expires_seconds=expires_seconds,
        )

        try:
            url = client.presigned_get_object(
                bucket_name=s.minio_bucket,
                object_name=object_key,
                expires=timedelta(seconds=expires_seconds),
            )

            if s.minio_public_url:
                parsed = urlparse(url)
                public = urlparse(s.minio_public_url)
                url = urlunparse(
                    parsed._replace(scheme=public.scheme, netloc=public.netloc)
                )

            logger.info(
                LogEvent.MINIO_STREAM_DONE,
                key=object_key,
                expires_seconds=expires_seconds,
            )
            return str(url)
        except S3Error as exc:
            logger.error(LogEvent.MINIO_STREAM_FAILED, key=object_key, error=str(exc))
            raise StorageError(
                f"Could not generate presigned URL for {object_key!r}: {exc}"
            ) from exc
        except Exception:
            logger.exception(LogEvent.MINIO_STREAM_FAILED, key=object_key)
            raise
