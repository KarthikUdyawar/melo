# app/services/storage.py
import logging
from pathlib import Path

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

logger = logging.getLogger(__name__)


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
    try:
        if not client.bucket_exists(s.minio_bucket):
            client.make_bucket(s.minio_bucket)
            logger.info("Created MinIO bucket: %s", s.minio_bucket)
        else:
            logger.debug("MinIO bucket already exists: %s", s.minio_bucket)
    except S3Error as exc:
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

    try:
        client.fput_object(
            bucket_name=s.minio_bucket,
            object_name=object_key,
            file_path=str(local_path),
            content_type="audio/mpeg",
        )
        logger.info("Uploaded %s → %s/%s", local_path, s.minio_bucket, object_key)
    except S3Error as exc:
        raise StorageError(
            f"Upload failed for {local_path!r} → {object_key!r}: {exc}"
        ) from exc

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

    s = get_settings()
    client = _client()

    try:
        url = client.presigned_get_object(
            bucket_name=s.minio_bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_seconds),
        )
        # Rewrite internal Docker hostname → externally accessible host
        if s.minio_public_url:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(url)
            public = urlparse(s.minio_public_url)
            url = urlunparse(
                parsed._replace(
                    scheme=public.scheme,
                    netloc=public.netloc,
                )
            )
        return url
    except S3Error as exc:
        raise StorageError(
            f"Could not generate presigned URL for {object_key!r}: {exc}"
        ) from exc
