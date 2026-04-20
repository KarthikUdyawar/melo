# app/workers/tasks.py
import logging
from uuid import UUID

from celery import Task

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


class _BaseTask(Task):
    """
    Shared base that holds one SQLAlchemy session per worker process.

    The session is created lazily on first use and reused across tasks
    in the same process — this avoids a connection-per-task overhead.
    Celery workers are long-lived processes, so this is safe.
    """

    _db = None

    @property
    def db(self):
        if self._db is None:
            from app.core.db import get_session_factory
            self._db = get_session_factory()()
        return self._db

    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=_BaseTask,
    name="app.workers.tasks.process_song",
    max_retries=3,
    default_retry_delay=10,  # seconds
    acks_late=True,
)
def process_song_task(
    self, song_id: str, url: str, start: float | None, end: float | None, speed: float
) -> dict:
    """
    Full ingest pipeline for a single song.

    Steps
    -----
    1. Mark DB record → ``processing``
    2. Download audio with yt-dlp  (→ /tmp/melo/<song_id>.mp3)
    3. Upload mp3 to MinIO          (→ songs/<song_id>.mp3)
    4. Update DB: file_url, duration, status → ``done``
    5. Clean up the local tmp file

    On any unhandled exception the record is marked ``failed`` and the
    exception is re-raised so Celery can log it and (optionally) retry.
    """
    from pathlib import Path

    from app.models.song import Song, SongStatus
    from app.services.downloader import DownloadError, download_audio
    from app.services.storage import StorageError, upload_file

    logger.info("process_song_task started: song_id=%s", song_id)

    # ── 1. Fetch the record and move to processing ───────────────────────────
    song = self.db.query(Song).filter(Song.id == UUID(song_id)).first()
    if song is None:
        # Record was deleted between enqueue and execution — nothing to do.
        logger.warning("Song %s not found in DB, skipping task.", song_id)
        return {"song_id": song_id, "status": "skipped"}

    song.status = SongStatus.processing
    self.db.commit()

    local_path: Path | None = None

    try:
        # ── 2. Download ──────────────────────────────────────────────────────
        local_path, duration = download_audio(url=url, song_id=song_id)

        # ── 3. Upload ────────────────────────────────────────────────────────
        object_key = f"{song_id}.mp3"
        upload_file(local_path=local_path, object_key=object_key)

        # ── 4. Update DB ─────────────────────────────────────────────────────
        song.file_url = object_key
        song.duration = duration
        song.status = SongStatus.done
        self.db.commit()

        logger.info("process_song_task done: song_id=%s", song_id)
        return {"song_id": song_id, "status": "done"}

    except (DownloadError, StorageError) as exc:
        # Known, non-retryable failures — mark failed immediately
        logger.error("process_song_task failed: song_id=%s error=%s", song_id, exc)
        _mark_failed(self.db, song)
        raise

    except Exception as exc:
        # Unknown errors — retry up to max_retries, then mark failed
        logger.exception("process_song_task unexpected error: song_id=%s", song_id)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_failed(self.db, song)
            raise

    finally:
        # ── 5. Cleanup ───────────────────────────────────────────────────────
        if local_path and local_path.exists():
            local_path.unlink(missing_ok=True)
            logger.debug("Cleaned up tmp file: %s", local_path)


def _mark_failed(db, song) -> None:
    """Best-effort status update to failed;
    swallows DB errors to avoid masking the original."""
    try:
        from app.models.song import SongStatus

        song.status = SongStatus.failed
        db.commit()
    except Exception:
        logger.exception("Could not mark song %s as failed", song.id)
        db.rollback()
