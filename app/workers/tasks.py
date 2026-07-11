"""Celery tasks for the Melo project."""

# app/workers/tasks.py

import time
from typing import Any, cast
from uuid import UUID

from billiard.einfo import ExceptionInfo
from celery import Task
from sqlalchemy.orm import Session

from app.core.log_events import LogEvent
from app.core.logging import get_logger
from app.core.metrics import songs_completed_total
from app.models.song import Song
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


class _BaseTask(Task):  # type: ignore[type-arg]
    """Base Celery task with a shared, lazily-created SQLAlchemy session."""

    _db = None

    @property
    def db(self) -> Session:
        if self._db is None:
            from app.core.db import get_session_factory

            self._db = get_session_factory()()
        return self._db

    def after_return(
        self,
        status: str,
        retval: Any,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: ExceptionInfo | None,
    ) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

        super().after_return(
            status,
            retval,
            task_id,
            args,
            kwargs,
            cast("ExceptionInfo", einfo),
        )


@celery_app.task(
    bind=True,
    base=_BaseTask,
    name="app.workers.tasks.process_song",
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_song_task(
    self: _BaseTask,
    song_id: str,
    url: str,
) -> dict[str, object]:
    """Process a song: download from YouTube, upload to MinIO, update DB.

    Args:
        song_id: UUID string of the song record.
        url: YouTube URL to download from.

    Returns:
        Status dictionary (e.g. ``{"song_id": "...", "status": "done"}``).
    """
    from pathlib import Path

    from app.models.song import Song, SongStatus
    from app.services.downloader import DownloadError, download_audio, probe_metadata
    from app.services.storage import StorageError, upload_file

    t_start = time.perf_counter()
    attempt = self.request.retries + 1

    logger.info(
        LogEvent.TASK_RECEIVED,
        song_id=song_id,
        attempt=attempt,
        max_retries=self.max_retries,
        url=url,
    )

    # ── 1. Fetch record and move to processing ───────────────────────────────
    song = self.db.query(Song).filter(Song.id == UUID(song_id)).first()

    if song is None:
        logger.warning(LogEvent.TASK_FAILED, song_id=song_id, reason="not_found")
        return {"song_id": song_id, "status": "skipped"}

    song.status = SongStatus.processing
    self.db.commit()

    logger.info(LogEvent.TASK_PROCESSING, song_id=song_id)
    # Reconstruct OTEL context from task headers (propagated at enqueue)
    _restore_trace_context(cast(dict[str, Any], self.request.headers))

    from app.core.tracing import get_tracer

    tracer = get_tracer(__name__)

    local_path: Path | None = None

    with tracer.start_as_current_span("celery.process_song") as span:
        span.set_attribute("song.id", song_id)
        try:
            # ── 2. Probe metadata ────────────────────────────────────────────────
            meta = probe_metadata(url)

            song.title = meta.get("title")
            song.duration = meta.get("duration")
            song.thumbnail_url = meta.get("thumbnail_url")
            song.channel = meta.get("channel")
            song.upload_date = meta.get("upload_date")
            self.db.commit()

            # ── 3. Dedup ─────────────────────────────────────────────────────────
            existing = (
                self.db.query(Song)
                .filter(
                    Song.youtube_id == song.youtube_id,
                    Song.status == SongStatus.done,
                    Song.id != song.id,
                )
                .first()
            )

            if existing is not None:
                logger.info(
                    LogEvent.TASK_DONE,
                    song_id=song_id,
                    via="dedup",
                    source_song_id=str(existing.id),
                )
                song.file_url = existing.file_url
                song.duration = existing.duration
                song.title = existing.title
                song.thumbnail_url = existing.thumbnail_url
                song.channel = existing.channel
                song.upload_date = existing.upload_date
                song.status = SongStatus.done
                self.db.commit()
                songs_completed_total.labels(status="done").inc()
                return {"song_id": song_id, "status": "done", "via": "dedup"}

            # ── 4. Download ──────────────────────────────────────────────────────
            local_path, duration = download_audio(url=url, song_id=song_id)

            if duration is not None:
                song.duration = duration

            # ── 5. Upload ────────────────────────────────────────────────────────
            object_key = f"{song_id}.mp3"
            upload_file(local_path=local_path, object_key=object_key)

            # ── 6. Update DB ─────────────────────────────────────────────────────
            song.file_url = object_key
            song.status = SongStatus.done
            self.db.commit()

            total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.info(
                LogEvent.TASK_DONE,
                song_id=song_id,
                duration_ms=total_ms,
                attempt=attempt,
            )
            songs_completed_total.labels(status="done").inc()
            return {"song_id": song_id, "status": "done"}

        except (DownloadError, StorageError) as exc:
            total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error(
                LogEvent.TASK_FAILED,
                song_id=song_id,
                duration_ms=total_ms,
                attempt=attempt,
                error=str(exc),
            )
            _mark_failed(self.db, song)
            songs_completed_total.labels(status="failed").inc()
            raise

        except Exception as exc:
            total_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.exception(
                LogEvent.TASK_FAILED,
                song_id=song_id,
                duration_ms=total_ms,
                attempt=attempt,
                error=str(exc),
            )
            try:
                logger.warning(LogEvent.TASK_RETRY, song_id=song_id, attempt=attempt)
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                logger.error(
                    LogEvent.TASK_FAILED, song_id=song_id, reason="max_retries_exceeded"
                )
                _mark_failed(self.db, song)
                raise

        finally:
            if local_path:
                try:
                    local_path.unlink(missing_ok=True)
                except Exception:
                    logger.exception(
                        "task_cleanup_failed", song_id=song_id, path=str(local_path)
                    )


def _mark_failed(db: Session, song: Song) -> None:
    """Mark a song record as failed. Best-effort — swallows DB errors.

    Args:
        db: SQLAlchemy session.
        song: Song model instance to update.
    """
    try:
        from app.models.song import SongStatus

        song.status = SongStatus.failed
        db.commit()
    except Exception:
        logger.exception("mark_failed_error", song_id=str(song.id))
        db.rollback()


def _restore_trace_context(headers: dict[str, Any] | None) -> None:
    """Reconstruct OTEL trace context from Celery task headers."""
    try:
        from opentelemetry import context
        from opentelemetry.propagate import extract

        carrier: dict[str, Any] = dict(headers) if headers is not None else {}
        ctx = extract(carrier)
        context.attach(ctx)
    except Exception:
        logger.debug(
            "Failed to restore OpenTelemetry trace context",
            headers=headers is not None,
            exc_info=True,
        )
