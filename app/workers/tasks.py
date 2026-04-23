# app/workers/tasks.py
"""
Celery tasks for Melo.

Worker logs emit structured JSON with fields: task_name, song_id, status, duration_ms.
"""

import time
from uuid import UUID

from celery import Task

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


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

    task_name = "process_song"
    t_start = time.perf_counter()
    
    attempt = self.request.retries + 1
    max_retries = self.max_retries

    logger.info(
        "task_start",
        task_name=task_name,
        song_id=song_id,
        attempt=attempt,
        max_retries=max_retries,
        url=url,
    )

    # ── 1. Fetch record and move to processing ───────────────────────────────
    song = self.db.query(Song).filter(Song.id == UUID(song_id)).first()
    
    if song is None:
        # Record was deleted between enqueue and execution — nothing to do.
        logger.warning(
            "task_skip",
            task_name=task_name,
            song_id=song_id,
            reason="not_found",
        )
        return {"song_id": song_id, "status": "skipped"}

    logger.debug(
        "db_record_loaded",
        task_name=task_name,
        song_id=song_id,
        current_status=str(song.status),
    )
    
    song.status = SongStatus.processing
    self.db.commit()
    
    logger.debug(
        "db_status_updated",
        task_name=task_name,
        song_id=song_id,
        new_status="processing",
    )

    local_path: Path | None = None

    try:
        # ── 2. Download ──────────────────────────────────────────────────────
        t_dl = time.perf_counter()
        logger.info("step_start", step="download", song_id=song_id)
        
        local_path, duration = download_audio(url=url, song_id=song_id)
        
        logger.info(
            "step_complete",
            step="download",
            song_id=song_id,
            duration_s=duration,
            elapsed_ms=round((time.perf_counter() - t_dl) * 1000, 2),
            path=str(local_path),
        )

        # ── 3. Upload ────────────────────────────────────────────────────────
        t_up = time.perf_counter()
        object_key = f"{song_id}.mp3"
        
        logger.info("step_start", step="upload", song_id=song_id, key=object_key)
        
        upload_file(local_path=local_path, object_key=object_key)
        
        logger.info(
            "step_complete",
            step="upload",
            song_id=song_id,
            key=object_key,
            elapsed_ms=round((time.perf_counter() - t_up) * 1000, 2),
        )

        # ── 4. Update DB ─────────────────────────────────────────────────────
        t_db = time.perf_counter()

        song.file_url = object_key
        song.duration = duration
        song.status = SongStatus.done
        self.db.commit()

        logger.info(
            "step_complete",
            step="db_update",
            song_id=song_id,
            status="done",
            elapsed_ms=round((time.perf_counter() - t_db) * 1000, 2),
        )
        
        total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        logger.info(
            "task_done",
            task_name=task_name,
            song_id=song_id,
            status="done",
            duration_ms=total_ms,
            attempt=attempt,
        )

        return {"song_id": song_id, "status": "done"}

    except (DownloadError, StorageError) as exc:
        # Known, non-retryable failures — mark failed immediately
        total_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.error(
            "task_failed",
            task_name=task_name,
            song_id=song_id,
            status="failed",
            duration_ms=total_ms,
            attempt=attempt,
            error=str(exc),
        )
        _mark_failed(self.db, song)
        raise

    except Exception as exc:
        # Unknown errors — retry up to max_retries, then mark failed
        total_ms = round((time.perf_counter() - t_start) * 1000, 2)

        logger.exception(
            "task_error",
            task_name=task_name,
            song_id=song_id,
            status="error",
            duration_ms=total_ms,
            attempt=attempt,
            error=str(exc),
        )
        try:
            logger.warning(
                "task_retrying",
                task_name=task_name,
                song_id=song_id,
                attempt=attempt,
                next_attempt=attempt + 1,
            )
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "task_max_retries_exceeded",
                task_name=task_name,
                song_id=song_id,
            )
            _mark_failed(self.db, song)
            raise

    finally:
        # ── 5. Cleanup ───────────────────────────────────────────────────────
        if local_path:
            try:
                if local_path.exists():
                    local_path.unlink(missing_ok=True)
                    logger.debug(
                        "task_cleanup_success",
                        task_name=task_name,
                        song_id=song_id,
                        path=str(local_path),
                    )
                else:
                    logger.debug(
                        "task_cleanup_skipped",
                        task_name=task_name,
                        song_id=song_id,
                        reason="file_not_found",
                    )
            except Exception:
                logger.exception(
                    "task_cleanup_failed",
                    task_name=task_name,
                    song_id=song_id,
                    path=str(local_path),
                )


def _mark_failed(db, song) -> None:
    """Best-effort status update to failed; swallows DB errors 
    to avoid masking the original."""
    try:
        from app.models.song import SongStatus

        song.status = SongStatus.failed
        db.commit()
    except Exception:
        logger.exception("mark_failed_error", song_id=str(song.id))
        db.rollback()
