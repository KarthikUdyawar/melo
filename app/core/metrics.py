"""Prometheus metric definitions — single source of truth.

All metric objects live here. Nothing imports prometheus_client elsewhere.
"""

# app/core/metrics.py
from prometheus_client import Counter, Gauge, Histogram

# ── Counters ──────────────────────────────────────────────────────────────────

songs_submitted_total = Counter(
    "songs_submitted_total",
    "Songs submitted via POST /songs",
)

songs_completed_total = Counter(
    "songs_completed_total",
    "Songs that finished processing",
    labelnames=["status"],  # done | failed
)

favorites_toggled_total = Counter(
    "favorites_toggled_total",
    "Favorite add/remove actions",
    labelnames=["action"],  # add | remove
)

playlist_ops_total = Counter(
    "playlist_ops_total",
    "Playlist CRUD operations",
    labelnames=["action"],  # create | delete | add_song | remove_song
)

# ── Gauges (polled every 30 s by background job) ──────────────────────────────

celery_queue_depth = Gauge(
    "celery_queue_depth",
    "Number of tasks waiting in the Celery queue",
)

celery_active_tasks = Gauge(
    "celery_active_tasks",
    "Number of Celery tasks currently executing",
)

minio_bucket_size_bytes = Gauge(
    "minio_bucket_size_bytes",
    "Total size of all objects in the MinIO bucket",
)

songs_by_status_total = Gauge(
    "songs_by_status",
    "Song count broken down by processing status",
    labelnames=["status"],  # pending | processing | done | failed
)

# ── Histograms ────────────────────────────────────────────────────────────────

download_duration_seconds = Histogram(
    "download_duration_seconds",
    "Time spent downloading audio via yt-dlp",
)

ffmpeg_duration_seconds = Histogram(
    "ffmpeg_duration_seconds",
    "Time spent in FFmpeg operations",
    labelnames=["op"],  # trim | speed | trim_speed
)

minio_upload_duration_seconds = Histogram(
    "minio_upload_duration_seconds",
    "Time spent uploading files to MinIO",
)

stream_duration_seconds = Histogram(
    "stream_duration_seconds",
    "Time spent serving audio stream responses",
)
