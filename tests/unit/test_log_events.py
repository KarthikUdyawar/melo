"""Tests for LogEvent enum — all expected members must exist."""

# tests/unit/test_log_events.py
import pytest

from app.core.log_events import LogEvent


@pytest.mark.parametrize(
    "member",
    [
        # Request lifecycle
        "REQUEST_STARTED",
        "REQUEST_FINISHED",
        "REQUEST_FAILED",
        # Song API
        "SONG_SUBMITTED",
        "SONG_NOT_FOUND",
        "SONG_DELETED",
        "SONG_STREAM_STARTED",
        "SONG_STREAM_FAILED",
        "PREVIEW_FETCHED",
        "PREVIEW_FAILED",
        # Worker / task
        "TASK_RECEIVED",
        "TASK_PROCESSING",
        "TASK_DONE",
        "TASK_FAILED",
        "TASK_RETRY",
        # Download
        "DOWNLOAD_STARTED",
        "DOWNLOAD_DONE",
        "DOWNLOAD_FAILED",
        # FFmpeg
        "FFMPEG_TRIM_STARTED",
        "FFMPEG_TRIM_DONE",
        "FFMPEG_SPEED_STARTED",
        "FFMPEG_SPEED_DONE",
        "FFMPEG_FAILED",
        # Storage
        "MINIO_UPLOAD_STARTED",
        "MINIO_UPLOAD_DONE",
        "MINIO_UPLOAD_FAILED",
        "MINIO_STREAM_STARTED",
        "MINIO_STREAM_FAILED",
        # Log rotation
        "LOG_ROTATED",
        "LOG_COMPRESSED",
        "LOG_BACKUP_UPLOADED",
        "LOG_BACKUP_CLEANED",
        # Favorites
        "FAVORITE_ADDED",
        "FAVORITE_REMOVED",
        # Playlists
        "PLAYLIST_CREATED",
        "PLAYLIST_DELETED",
        "PLAYLIST_SONG_ADDED",
        "PLAYLIST_SONG_REMOVED",
        # Health
        "HEALTH_CHECKED",
        "HEALTH_DEGRADED",
    ],
)
def test_log_event_member_exists(member: str) -> None:
    assert hasattr(LogEvent, member), f"LogEvent missing member: {member}"


def test_log_event_values_are_strings() -> None:
    for member in LogEvent:
        assert isinstance(member.value, str), f"{member.name} value must be str"


def test_log_event_value_is_lowercase_snake() -> None:
    import re

    pattern = re.compile(r"^[a-z][a-z0-9_]*$")
    for member in LogEvent:
        assert (
            member.value == member.value.lower()
        ), f"{member.name} value must be lowercase: {member.value!r}"
        assert pattern.match(
            member.value
        ), f"{member.name} value must be lowercase snake_case: {member.value!r}"
