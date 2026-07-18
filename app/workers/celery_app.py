"""Celery application setup for the Melo project."""

# app/workers/celery_app.py
import os

from celery import Celery
from celery.signals import worker_init, worker_ready

from app.core.logging import configure_logging, get_logger

# Configure logging before any task module imports emit log lines.
configure_logging("worker")

logger = get_logger(__name__)

celery_app = Celery(
    "melo",
    broker=os.getenv("CELERY_BROKER", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_BACKEND", "redis://redis:6379/1"),
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_default_queue="melo",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@worker_init.connect
def on_worker_init(**kwargs: object) -> None:
    """Re-run logging and profiling setup after worker process fork.

    Resets the ``_CONFIGURED`` guards so the child process re-opens file
    handlers in its own fd space and reinitializes tracing with the worker
    service name, then starts Pyroscope profiling.

    Args:
        **kwargs: Celery signal arguments (unused).
    """
    import app.core.logging as log_mod
    import app.core.tracing as tracing_mod
    from app.core.profiling import configure_pyroscope
    from app.core.tracing import configure_tracing

    log_mod._CONFIGURED = False
    tracing_mod._CONFIGURED = False
    configure_tracing("melo.worker")
    configure_logging("worker")
    configure_pyroscope("melo.worker")
    logger.info("worker_logging_ready")


@worker_ready.connect
def on_worker_ready(**kwargs: object) -> None:
    """Start log rotation and ensure MinIO bucket exists before first task.

    Args:
        **kwargs: Celery signal arguments (unused).
    """
    from app.core.log_manager import LogManager
    from app.services.storage import StorageError, ensure_bucket_exists

    LogManager.from_settings("worker")

    try:
        ensure_bucket_exists()
        logger.info("worker_ready", bucket_check="ok")
    except StorageError:
        logger.exception("worker_ready_bucket_failed")
