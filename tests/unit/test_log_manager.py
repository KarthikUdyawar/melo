"""Tests for LogManager — rotation, gzip, MinIO upload, retention cleanup."""

# tests/unit/test_log_manager.py
import gzip
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def log_file(tmp_path: Path) -> Path:
    p = tmp_path / "api.jsonl"
    p.write_text("")
    return p


@pytest.fixture()
def manager(log_file: Path):
    """LogManager with tiny thresholds for testing; APScheduler disabled."""
    from app.core.log_manager import LogManager

    return LogManager(
        log_file=log_file,
        service="api",
        max_size_mb=1,
        max_age_hours=1,
        backup_bucket="melo-log-backups",
        retention_days=90,
        start_scheduler=False,
    )


# ── Roll triggers ─────────────────────────────────────────────────────────────


def test_should_roll_false_when_small_and_young(manager, log_file):
    # fresh empty file — should NOT roll
    assert manager.should_roll() is False


def test_should_roll_true_when_size_exceeded(manager, log_file):
    # write > 1 MB
    log_file.write_bytes(b"x" * (1 * 1024 * 1024 + 1))
    assert manager.should_roll() is True


def test_should_roll_true_when_age_exceeded(manager, log_file):
    # fake mtime > 1 hour ago
    old_mtime = time.time() - (61 * 60)
    os.utime(log_file, (old_mtime, old_mtime))
    assert manager.should_roll() is True


# ── Roll sequence ─────────────────────────────────────────────────────────────


def test_roll_produces_gz_file(manager, log_file, tmp_path):
    """Upload mock receives a .gz path — proves gz was created during roll."""
    log_file.write_text('{"event":"test"}\n')

    captured_paths: list[Path] = []

    def capture(gz_path: Path, object_name: str) -> None:
        # Save a copy before roll() deletes the local .gz
        captured_paths.append(gz_path)

    with patch.object(manager, "_upload_to_minio", side_effect=capture):
        manager.roll()

    assert len(captured_paths) == 1
    assert captured_paths[0].name.endswith(".jsonl.gz")


def test_roll_gz_is_valid_gzip(manager, log_file, tmp_path):
    """gz passed to upload is a valid gzip archive containing original content."""
    log_file.write_text('{"event":"test"}\n')

    saved_gz = tmp_path / "saved.gz"

    def capture(gz_path: Path, object_name: str) -> None:
        # Copy before roll() deletes it
        import shutil

        shutil.copy2(gz_path, saved_gz)

    with patch.object(manager, "_upload_to_minio", side_effect=capture):
        manager.roll()

    with gzip.open(saved_gz) as f:
        content = f.read()
    assert b"test" in content


def test_roll_deletes_local_gz_after_upload(manager, log_file, tmp_path):
    log_file.write_text('{"event":"test"}\n')

    with patch.object(manager, "_upload_to_minio"):
        manager.roll()

    gz_files = list(tmp_path.glob("*.gz"))
    assert gz_files == [], "local .gz must be deleted after upload"


def test_roll_opens_fresh_log_file(manager, log_file):
    log_file.write_text('{"event":"old"}\n')

    with patch.object(manager, "_upload_to_minio"):
        manager.roll()

    assert log_file.exists()
    assert log_file.read_text() == ""


def test_roll_calls_upload_with_correct_bucket_path(manager, log_file, tmp_path):
    log_file.write_text('{"event":"test"}\n')

    captured: list[tuple[str, str]] = []

    def fake_upload(gz_path: Path, object_name: str) -> None:
        captured.append((str(gz_path), object_name))

    with patch.object(manager, "_upload_to_minio", side_effect=fake_upload):
        manager.roll()

    assert len(captured) == 1
    _gz_path, obj_name = captured[0]
    # path: api/<YYYY>/<MM>/<filename>.gz
    parts = obj_name.split("/")
    assert parts[0] == "api"
    assert len(parts[1]) == 4  # year
    assert len(parts[2]) == 2  # month
    assert parts[3].endswith(".jsonl.gz")


# ── Retention cleanup ─────────────────────────────────────────────────────────


def test_cleanup_deletes_objects_older_than_retention(manager):
    old_date = datetime.now(UTC) - timedelta(days=91)
    new_date = datetime.now(UTC) - timedelta(days=10)

    old_obj = MagicMock()
    old_obj.object_name = "api/2024/01/api.old.jsonl.gz"
    old_obj.last_modified = old_date

    new_obj = MagicMock()
    new_obj.object_name = "api/2025/06/api.new.jsonl.gz"
    new_obj.last_modified = new_date

    mock_client = MagicMock()
    mock_client.list_objects.return_value = [old_obj, new_obj]

    with patch.object(manager, "_minio_client", return_value=mock_client):
        deleted = manager.cleanup_old_backups()

    mock_client.remove_object.assert_called_once_with(
        "melo-log-backups", "api/2024/01/api.old.jsonl.gz"
    )
    assert deleted == 1


def test_cleanup_preserves_objects_within_retention(manager):
    new_obj = MagicMock()
    new_obj.object_name = "api/2025/06/api.new.jsonl.gz"
    new_obj.last_modified = datetime.now(UTC) - timedelta(days=10)

    mock_client = MagicMock()
    mock_client.list_objects.return_value = [new_obj]

    with patch.object(manager, "_minio_client", return_value=mock_client):
        deleted = manager.cleanup_old_backups()

    mock_client.remove_object.assert_not_called()
    assert deleted == 0

def test_roll_reopens_handler_before_gzip_runs(manager, log_file):
    """Handler swap must happen before gzip touches the renamed file —
    proves the fix for the data-loss window CodeRabbit flagged."""
    from app.core import log_manager as log_manager_mod

    log_file.write_text('{"event":"test"}\n')
    call_order: list[str] = []

    def fake_reopen():
        call_order.append("reopen_file_handler")
        return True  # must signal success or roll() aborts before gzip

    def fake_gzip(source, dest):
        call_order.append("_gzip_file")
        dest.write_bytes(b"")  # roll() still needs a dest file to unlink

    with (
        patch("app.core.logging.reopen_file_handler", side_effect=fake_reopen),
        patch.object(log_manager_mod, "_gzip_file", side_effect=fake_gzip),
        patch.object(manager, "_upload_to_minio"),
    ):
        manager.roll()

    assert call_order == ["reopen_file_handler", "_gzip_file"]


def test_roll_active_file_writable_during_gzip(manager, log_file, tmp_path):
    """A write to the active log file mid-gzip must land in the fresh file,
    not the one being archived and then deleted."""
    from app.core import log_manager as log_manager_mod

    log_file.write_text('{"event":"old"}\n')

    def fake_gzip(source, dest):
        # Simulate a log line arriving while gzip/upload is in flight —
        # by this point roll() must have already reopened the handler
        # onto the fresh log_file.
        log_file.write_text('{"event":"during_roll"}\n')
        dest.write_bytes(b"")

    with (
        patch.object(log_manager_mod, "_gzip_file", side_effect=fake_gzip),
        patch.object(manager, "_upload_to_minio"),
    ):
        manager.roll()

    assert log_file.read_text() == '{"event":"during_roll"}\n'

def test_roll_aborts_and_restores_when_handler_reopen_fails(manager, log_file):
    """If reopen_file_handler() fails, rotation must restore the renamed
    file as active and skip gzip/upload — never delete a file the old
    handler is still writing into."""
    from app.core import log_manager as log_manager_mod

    original_content = '{"event":"important"}\n'
    log_file.write_text(original_content)

    with (
        patch("app.core.logging.reopen_file_handler", return_value=False),
        patch.object(log_manager_mod, "_gzip_file") as mock_gzip,
        patch.object(manager, "_upload_to_minio") as mock_upload,
    ):
        manager.roll()

    mock_gzip.assert_not_called()
    mock_upload.assert_not_called()
    assert log_file.exists()
    assert log_file.read_text() == original_content
