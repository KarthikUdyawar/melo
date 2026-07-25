"""Background poller for gauge metrics — polls every 30s.

Updates: celery_queue_depth, celery_active_tasks,
minio_bucket_size_bytes, songs_by_status_total.
"""

# app/core/pollers.py
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.logging import get_logger

logger = get_logger(__name__)


def _poll_gauges() -> None:
    """Single poll cycle — refresh all gauge metrics. Best-effort per metric."""
    _poll_celery_gauges()
    _poll_minio_gauge()
    _poll_song_status_gauge()


def _poll_celery_gauges() -> None:
    from app.core.metrics import celery_active_tasks, celery_queue_depth

    try:
        from app.workers.celery_app import celery_app

        inspect = celery_app.control.inspect(timeout=2.0)

        active = inspect.active() or {}
        celery_active_tasks.set(sum(len(tasks) for tasks in active.values()))

        reserved = inspect.reserved() or {}
        queue_depth = sum(len(tasks) for tasks in reserved.values())
        celery_queue_depth.set(queue_depth)
    except Exception:
        logger.exception("poll_celery_gauges_failed")


def _poll_minio_gauge() -> None:
    from app.core.metrics import minio_bucket_size_bytes

    try:
        from app.core.config import get_settings
        from app.services.storage import _client

        s = get_settings()
        client = _client()
        total = sum(
            obj.size or 0 for obj in client.list_objects(s.minio_bucket, recursive=True)
        )
        minio_bucket_size_bytes.set(total)
    except Exception:
        logger.exception("poll_minio_gauge_failed")


def _poll_song_status_gauge() -> None:
    from app.core.metrics import songs_by_status_total

    try:
        from sqlalchemy import func

        from app.core.db import get_session_factory
        from app.models.song import Song, SongStatus

        session = get_session_factory()()
        try:
            rows = (
                session.query(Song.status, func.count(Song.id))
                .filter(Song.deleted_at.is_(None))
                .group_by(Song.status)
                .all()
            )

            counts: dict[SongStatus, int] = {
                status: count for status, count in rows
            }
            for status in SongStatus:
                songs_by_status_total.labels(status=status.value).set(
                    counts.get(status, 0)
                )
        finally:
            session.close()
    except Exception:
        logger.exception("poll_song_status_gauge_failed")

def start_gauge_poller() -> BackgroundScheduler:
    """Start APScheduler background job — polls gauges every 30s.

    Returns:
        Running BackgroundScheduler instance.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(_poll_gauges, "interval", seconds=30)
    scheduler.start()
    return scheduler
