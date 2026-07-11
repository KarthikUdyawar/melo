"""Log file rotation, compression, and backup for Melo.

Responsibilities (single class, one per service):
  - Check size and age thresholds every 60 s (background thread via APScheduler)
  - On roll: close → rename → gzip → upload MinIO → delete local → open fresh
  - Daily cleanup: delete MinIO backup objects older than retention_days

Usage::

    manager = LogManager.from_settings(service="api")
    manager.start()   # begins background check loop

The ``start_scheduler=False`` constructor flag disables scheduling for tests.
"""

# app/core/log_manager.py
import gzip
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minio import Minio


class LogManager:
    """Manages log rotation, gzip compression, MinIO backup, and retention.

    Args:
        log_file: Path to the active JSONL log file.
        service: Service label used as the MinIO prefix (``"api"`` or
            ``"worker"``).
        max_size_mb: Roll when file exceeds this size in megabytes.
        max_age_hours: Roll when file mtime is older than this many hours.
        backup_bucket: MinIO bucket name for compressed log backups.
        retention_days: Delete MinIO backups older than this many days.
        start_scheduler: If ``True``, start APScheduler background loop.
    """

    def __init__(
        self,
        log_file: Path,
        service: str,
        max_size_mb: float,
        max_age_hours: float,
        backup_bucket: str,
        retention_days: int,
        *,
        start_scheduler: bool = True,
    ) -> None:
        """Initialize the log manager.

        Configure log rotation thresholds and optionally start the background
        scheduler for automatic rotation and backup cleanup.
        """
        self._log_file = Path(log_file)
        self._service = service
        self._max_size_bytes = int(max_size_mb * 1024 * 1024)
        self._max_age_seconds = max_age_hours * 3600
        self._backup_bucket = backup_bucket
        self._retention_days = retention_days
        self._scheduler = None  # Store reference for clean shutdown

        # Ensure directory/file exist when possible.
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            self._log_file.touch(exist_ok=True)
        except PermissionError:
            # Logging subsystem already falls back to stdout.
            pass

        if start_scheduler:
            self._start_background_scheduler()

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_settings(cls, service: str) -> "LogManager":
        """Build a ``LogManager`` from application settings.

        Args:
            service: ``"api"`` or ``"worker"``.

        Returns:
            Configured ``LogManager`` with scheduler started.
        """
        from app.core.config import get_settings

        s = get_settings()
        log_file = Path(s.log_file_path).parent / f"{service}.jsonl"
        return cls(
            log_file=log_file,
            service=service,
            max_size_mb=s.log_max_size_mb,
            max_age_hours=s.log_max_age_hours,
            backup_bucket=s.log_backup_bucket,
            retention_days=s.log_retention_days,
            start_scheduler=True,
        )

    # ── Public interface ──────────────────────────────────────────────────────

    def should_roll(self) -> bool:
        """Return ``True`` if the log file should be rolled.

        Checks:
          1. File size >= max_size_bytes
          2. File mtime age >= max_age_seconds
        """
        if not self._log_file.exists():
            return False

        stat = self._log_file.stat()
        size_exceeded = stat.st_size >= self._max_size_bytes
        age_exceeded = (time.time() - stat.st_mtime) >= self._max_age_seconds

        return size_exceeded or age_exceeded

    def roll(self) -> None:
        """Execute the full roll sequence.

        Sequence:
          1. Rename active file → timestamped name
          2. Gzip the renamed file in-process
          3. Upload .gz to MinIO
          4. Delete local .gz
          5. Open fresh active file (touch)
          6. Emit log events
        """
        from app.core.log_events import LogEvent
        from app.core.logging import get_logger

        logger = get_logger(__name__)

        if not self._log_file.exists():
            logger.warning(
                "log_roll_skipped_missing_file",
                service=self._service,
            )
            return

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        rolled_name = f"{self._service}.{timestamp}.jsonl"
        rolled_path = self._log_file.parent / rolled_name
        gz_path = rolled_path.with_suffix(".jsonl.gz")

        # 1. Rename
        self._log_file.rename(rolled_path)

        # 2. Gzip in-process
        _gzip_file(rolled_path, gz_path)
        rolled_path.unlink(missing_ok=True)

        # 3. Upload to MinIO
        dt = datetime.now(UTC)
        object_name = (
            f"{self._service}/{dt.strftime('%Y')}/{dt.strftime('%m')}/{gz_path.name}"
        )
        self._upload_to_minio(gz_path, object_name)

        # 4. Delete local .gz
        gz_path.unlink(missing_ok=True)

        # 5. Open fresh file
        self._log_file.touch()

        # 6. Log events
        logger.info(LogEvent.LOG_ROTATED, rolled=rolled_name, service=self._service)
        logger.info(
            LogEvent.LOG_BACKUP_UPLOADED,
            bucket=self._backup_bucket,
            object=object_name,
        )

    def shutdown(self) -> None:
        """Stop the background scheduler, if running.

        Safe to call multiple times or when no scheduler was started.
        """
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def cleanup_old_backups(self) -> int:
        """Delete MinIO backup objects older than ``retention_days``.

        Returns:
            Number of objects deleted.
        """
        from app.core.log_events import LogEvent
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        client = self._minio_client()
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)

        objects = list(client.list_objects(self._backup_bucket, recursive=True))
        deleted = 0
        for obj in objects:
            last_modified = obj.last_modified
            if last_modified.tzinfo is None:
                last_modified = last_modified.replace(tzinfo=UTC)
            if last_modified < cutoff:
                client.remove_object(self._backup_bucket, obj.object_name)
                deleted += 1

        logger.info(
            LogEvent.LOG_BACKUP_CLEANED,
            deleted_count=deleted,
            service=self._service,
        )
        return deleted

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _upload_to_minio(self, gz_path: Path, object_name: str) -> None:
        """Upload *gz_path* to MinIO at *object_name*."""
        client = self._minio_client()
        client.fput_object(
            self._backup_bucket,
            object_name,
            str(gz_path),
            content_type="application/gzip",
        )

    def _minio_client(self) -> "Minio":
        """Return a configured MinIO client."""
        from app.services.storage import _client

        return _client()

    def _check_and_roll(self) -> None:
        """Called by APScheduler every 60 s — rolls if threshold exceeded."""
        if self.should_roll():
            try:
                self.roll()
            except Exception:  # noqa: BLE001
                from app.core.logging import get_logger

                get_logger(__name__).exception("log_roll_failed")

    def _start_background_scheduler(self) -> None:
        """Start APScheduler with a 60 s interval job + daily cleanup."""
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()
        scheduler.add_job(self._check_and_roll, "interval", seconds=60)
        scheduler.add_job(
            self.cleanup_old_backups,
            "cron",
            hour=2,
            minute=0,
            timezone="UTC",
        )
        scheduler.start()
        self._scheduler = scheduler


# ── Module-level helpers ──────────────────────────────────────────────────────


def _gzip_file(source: Path, dest: Path) -> None:
    """Compress *source* → *dest* using gzip in-process (no shell)."""
    with source.open("rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
