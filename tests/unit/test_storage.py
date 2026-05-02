"""
Unit tests for app/services/storage.py

All Minio calls are mocked — no real S3 connection.
Tests cover:
- ensure_bucket_exists: bucket missing → create, bucket exists → skip, S3Error
- upload_file: success, file missing, S3Error, unexpected error
- get_presigned_url: success, url rewrite with minio_public_url, S3Error
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from app.services.storage import (
    StorageError,
    ensure_bucket_exists,
    get_presigned_url,
    upload_file,
)


def _make_s3_error() -> S3Error:
    return S3Error(
        code="NoSuchBucket",
        message="The specified bucket does not exist",
        resource="/songs",
        request_id="test-req",
        host_id="test-host",
        response=MagicMock(status=404, headers={}, data=b""),
    )


@pytest.fixture()
def mock_client():
    with patch("app.services.storage._client") as mock:
        yield mock.return_value


@pytest.fixture()
def mock_settings():
    with patch("app.services.storage.get_settings") as mock:
        s = MagicMock()
        s.minio_bucket = "songs"
        s.minio_endpoint = "localhost:9000"
        s.minio_public_url = None
        mock.return_value = s
        yield s


# ── ensure_bucket_exists ──────────────────────────────────────────────────────


class TestEnsureBucketExists:
    def test_creates_bucket_when_missing(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_client.bucket_exists.return_value = False
        ensure_bucket_exists()
        mock_client.make_bucket.assert_called_once_with("songs")

    def test_skips_create_when_exists(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_client.bucket_exists.return_value = True
        ensure_bucket_exists()
        mock_client.make_bucket.assert_not_called()

    def test_raises_storage_error_on_s3_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_client.bucket_exists.side_effect = _make_s3_error()
        with pytest.raises(StorageError, match="Could not ensure bucket"):
            ensure_bucket_exists()


# ── upload_file ───────────────────────────────────────────────────────────────


class TestUploadFile:
    def test_success(
        self, tmp_path: Path, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mp3 = tmp_path / "song.mp3"
        mp3.write_bytes(b"\xff\xfb" * 100)

        result = upload_file(local_path=mp3, object_key="abc.mp3")

        assert result == "abc.mp3"
        mock_client.fput_object.assert_called_once_with(
            bucket_name="songs",
            object_name="abc.mp3",
            file_path=str(mp3),
            content_type="audio/mpeg",
        )

    def test_raises_when_file_missing(
        self, tmp_path: Path, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        missing = tmp_path / "ghost.mp3"
        with pytest.raises(StorageError, match="does not exist"):
            upload_file(local_path=missing, object_key="ghost.mp3")
        mock_client.fput_object.assert_not_called()

    def test_raises_storage_error_on_s3_error(
        self, tmp_path: Path, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mp3 = tmp_path / "song.mp3"
        mp3.write_bytes(b"\xff\xfb" * 100)
        mock_client.fput_object.side_effect = _make_s3_error()

        with pytest.raises(StorageError, match="Upload failed"):
            upload_file(local_path=mp3, object_key="abc.mp3")

    def test_reraises_unexpected_exception(
        self, tmp_path: Path, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mp3 = tmp_path / "song.mp3"
        mp3.write_bytes(b"\xff\xfb" * 100)
        mock_client.fput_object.side_effect = RuntimeError("disk full")

        with pytest.raises(RuntimeError, match="disk full"):
            upload_file(local_path=mp3, object_key="abc.mp3")


# ── get_presigned_url ─────────────────────────────────────────────────────────


class TestGetPresignedUrl:
    def test_success(self, mock_client: MagicMock, mock_settings: MagicMock) -> None:
        mock_client.presigned_get_object.return_value = (
            "http://localhost:9000/songs/abc.mp3?X-Amz-Signature=xxx"
        )
        url = get_presigned_url("abc.mp3", expires_seconds=3600)
        assert "abc.mp3" in url
        assert url.startswith("http")

    def test_rewrites_url_when_public_url_set(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.minio_public_url = "https://minio.example.com"
        mock_client.presigned_get_object.return_value = (
            "http://minio:9000/songs/abc.mp3?X-Amz-Signature=xxx"
        )
        url = get_presigned_url("abc.mp3")
        assert url.startswith("https://minio.example.com")

    def test_no_rewrite_when_public_url_none(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_settings.minio_public_url = None
        internal = "http://minio:9000/songs/abc.mp3?sig=xxx"
        mock_client.presigned_get_object.return_value = internal
        url = get_presigned_url("abc.mp3")
        assert url == internal

    def test_raises_storage_error_on_s3_error(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_client.presigned_get_object.side_effect = _make_s3_error()
        with pytest.raises(StorageError, match="Could not generate presigned URL"):
            get_presigned_url("abc.mp3")

    def test_reraises_unexpected_exception(
        self, mock_client: MagicMock, mock_settings: MagicMock
    ) -> None:
        mock_client.presigned_get_object.side_effect = ConnectionError("timeout")
        with pytest.raises(ConnectionError):
            get_presigned_url("abc.mp3")
