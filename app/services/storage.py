# app/services/storage.py
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageError(Exception):
    """Raised when a MinIO operation fails."""


def _client() -> Minio:
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


def ensure_bucket_exists() -> None:
    """
    Create the configured bucket if it does not already exist.

    Called once at worker startup so tasks never have to check themselves.
    """
    s = get_settings()
    client = _client()

    logger.info(
        "ensure_bucket_start",
        bucket=s.minio_bucket,
        endpoint=s.minio_endpoint,
    )

    try:
        exists = client.bucket_exists(s.minio_bucket)

        logger.debug(
            "bucket_exists_check",
            bucket=s.minio_bucket,
            exists=exists,
        )

        if not exists:
            client.make_bucket(s.minio_bucket)
            logger.info("bucket_created", bucket=s.minio_bucket)
        else:
            logger.debug("bucket_exists", bucket=s.minio_bucket)

    except S3Error as exc:
        logger.error(
            "ensure_bucket_failed",
            bucket=s.minio_bucket,
            error=str(exc),
        )
        raise StorageError(
            f"Could not ensure bucket {s.minio_bucket!r}: {exc}"
        ) from exc


def upload_file(local_path: Path, object_key: str) -> str:
    """
    Upload *local_path* to MinIO at *object_key* inside the configured bucket.

    Args:
        local_path:  Absolute path to the file on disk.
        object_key:  Destination key, e.g. ``"songs/abc-123.mp3"``.

    Returns:
        The bare object key (callers can build URLs / presigned URLs from it).

    Raises:
        StorageError: on any S3 / IO error.
    """
    s = get_settings()
    client = _client()

    if not local_path.exists():
        logger.error(
            "upload_file_missing",
            path=str(local_path),
            key=object_key,
        )
        raise StorageError(f"File does not exist: {local_path}")

    file_size = local_path.stat().st_size

    logger.info(
        "upload_start",
        path=str(local_path),
        size=file_size,
        bucket=s.minio_bucket,
        key=object_key,
    )

    try:
        client.fput_object(
            bucket_name=s.minio_bucket,
            object_name=object_key,
            file_path=str(local_path),
            content_type="audio/mpeg",
        )
        logger.info(
            "upload_complete",
            path=str(local_path),
            size=file_size,
            bucket=s.minio_bucket,
            key=object_key,
        )
    except S3Error as exc:
        logger.error(
            "upload_failed_s3",
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
            "upload_failed_unexpected",
            path=str(local_path),
            bucket=s.minio_bucket,
            key=object_key,
        )
        raise

    return object_key


def get_presigned_url(object_key: str, expires_seconds: int = 3600) -> str:
    """
    Generate a presigned GET URL for *object_key*.

    Args:
        object_key:      e.g. ``"songs/abc-123.mp3"``
        expires_seconds: URL TTL in seconds (default 1 hour).

    Returns:
        A pre-signed HTTPS/HTTP URL string.

    Raises:
        StorageError: if MinIO rejects the request.
    """
    from datetime import timedelta
    from urllib.parse import urlparse, urlunparse

    s = get_settings()
    client = _client()

    logger.debug(
        "presigned_url_start",
        bucket=s.minio_bucket,
        key=object_key,
        expires_seconds=expires_seconds,
    )

    try:
        url = client.presigned_get_object(
            bucket_name=s.minio_bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_seconds),
        )

        logger.debug(
            "presigned_url_generated_internal",
            key=object_key,
            url=url,
        )

        # Rewrite internal Docker hostname → externally accessible host
        if s.minio_public_url:
            parsed = urlparse(url)
            public = urlparse(s.minio_public_url)

            rewritten_url = urlunparse(
                parsed._replace(
                    scheme=public.scheme,
                    netloc=public.netloc,
                )
            )

            logger.debug(
                "presigned_url_rewritten",
                original=url,
                rewritten=rewritten_url,
                public_base=s.minio_public_url,
            )

            url = rewritten_url

        logger.info(
            "presigned_url_ready",
            key=object_key,
            expires_seconds=expires_seconds,
        )
        return str(url)
    except S3Error as exc:
        logger.error(
            "presigned_url_failed",
            key=object_key,
            error=str(exc),
        )
        raise StorageError(
            f"Could not generate presigned URL for {object_key!r}: {exc}"
        ) from exc

    except Exception:
        logger.exception(
            "presigned_url_failed_unexpected",
            key=object_key,
        )
        raise
