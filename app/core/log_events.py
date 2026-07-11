"""Log event names for Melo — single source of truth.

Every structured log call must use a member of this enum.
No raw event-name strings anywhere else in the codebase.
"""

# app/core/log_events.py
from enum import StrEnum


class LogEvent(StrEnum):
    """Canonical log event identifiers.

    Values are lowercase snake_case strings that appear as the ``event``
    field in every structured log line.
    """

    # ── Request lifecycle ─────────────────────────────────────────────────────
    REQUEST_STARTED = "request_started"
    """HTTP request received by the server."""

    REQUEST_FINISHED = "request_finished"
    """HTTP response dispatched to the client."""

    REQUEST_FAILED = "request_failed"
    """Unhandled exception during request processing."""

    # ── Song API ──────────────────────────────────────────────────────────────
    SONG_SUBMITTED = "song_submitted"
    """New song accepted and queued for processing."""

    SONG_NOT_FOUND = "song_not_found"
    """Requested song ID does not exist or is soft-deleted."""

    SONG_DELETED = "song_deleted"
    """Song soft-deleted and MinIO object removed."""

    SONG_STREAM_STARTED = "song_stream_started"
    """Audio stream response initiated."""

    SONG_STREAM_FAILED = "song_stream_failed"
    """Audio stream failed (MinIO or FFmpeg error)."""

    PREVIEW_FETCHED = "preview_fetched"
    """YouTube metadata probe returned successfully."""

    PREVIEW_FAILED = "preview_failed"
    """YouTube metadata probe failed."""

    # ── Worker / task ─────────────────────────────────────────────────────────
    TASK_RECEIVED = "task_received"
    """Celery worker picked up a process_song_task."""

    TASK_PROCESSING = "task_processing"
    """Task status updated to processing in DB."""

    TASK_DONE = "task_done"
    """Task completed — file uploaded, status set to done."""

    TASK_FAILED = "task_failed"
    """Task failed after exhausting retries or non-retryable error."""

    TASK_RETRY = "task_retry"
    """Task will be retried after a transient error."""

    # ── Download ──────────────────────────────────────────────────────────────
    DOWNLOAD_STARTED = "download_started"
    """yt-dlp download initiated."""

    DOWNLOAD_DONE = "download_done"
    """yt-dlp download completed successfully."""

    DOWNLOAD_FAILED = "download_failed"
    """yt-dlp download failed."""

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    FFMPEG_TRIM_STARTED = "ffmpeg_trim_started"
    """FFmpeg trim operation started."""

    FFMPEG_TRIM_DONE = "ffmpeg_trim_done"
    """FFmpeg trim operation completed."""

    FFMPEG_SPEED_STARTED = "ffmpeg_speed_started"
    """FFmpeg atempo speed adjustment started."""

    FFMPEG_SPEED_DONE = "ffmpeg_speed_done"
    """FFmpeg atempo speed adjustment completed."""

    FFMPEG_FAILED = "ffmpeg_failed"
    """FFmpeg operation failed."""

    # ── Storage (MinIO) ───────────────────────────────────────────────────────
    MINIO_UPLOAD_STARTED = "minio_upload_started"
    """Upload to MinIO bucket initiated."""

    MINIO_UPLOAD_DONE = "minio_upload_done"
    """Upload to MinIO bucket completed."""

    MINIO_UPLOAD_FAILED = "minio_upload_failed"
    """Upload to MinIO bucket failed."""

    MINIO_STREAM_STARTED = "minio_stream_started"
    """Object retrieval from MinIO for streaming started."""

    MINIO_STREAM_FAILED = "minio_stream_failed"
    """Object retrieval from MinIO for streaming failed."""

    # ── Log rotation ──────────────────────────────────────────────────────────
    LOG_ROTATED = "log_rotated"
    """Log file rolled over (size or age threshold reached)."""

    LOG_COMPRESSED = "log_compressed"
    """Rolled log file compressed to .gz."""

    LOG_BACKUP_UPLOADED = "log_backup_uploaded"
    """Compressed log file uploaded to MinIO backup bucket."""

    LOG_BACKUP_CLEANED = "log_backup_cleaned"
    """Stale log backups deleted from MinIO (retention policy)."""

    # ── Favorites ─────────────────────────────────────────────────────────────
    FAVORITE_ADDED = "favorite_added"
    """Song marked as favorite."""

    FAVORITE_REMOVED = "favorite_removed"
    """Song removed from favorites."""

    # ── Playlists ─────────────────────────────────────────────────────────────
    PLAYLIST_CREATED = "playlist_created"
    """New playlist created."""

    PLAYLIST_DELETED = "playlist_deleted"
    """Playlist soft-deleted."""

    PLAYLIST_SONG_ADDED = "playlist_song_added"
    """Song added to playlist."""

    PLAYLIST_SONG_REMOVED = "playlist_song_removed"
    """Song removed from playlist."""

    # ── Health ────────────────────────────────────────────────────────────────
    HEALTH_CHECKED = "health_checked"
    """Health check completed (all services OK)."""

    HEALTH_DEGRADED = "health_degraded"
    """Health check completed with one or more degraded services."""
