"""Celery application setup for the Melo project.

This module creates and configures the Celery application instance with Redis
as both broker and backend. It also registers signal handlers for worker
lifecycle events (`worker_init` and `worker_ready`).
"""
# app/workers/celery_app.py
import os

from celery import Celery
from celery.signals import worker_init, worker_ready

# Configure structured logging before any other import so worker loggers
# are fully set up from the first line of every task module.
from app.core.logging import get_logger, setup_logging

setup_logging()

logger = get_logger(__name__)

celery_app = Celery(
    "melo",
    broker=os.getenv("CELERY_BROKER", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_BACKEND", "redis://redis:6379/1"),
    include=["app.workers.tasks"],
)

# Main Celery application instance

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
    """Re-run logging setup after worker process fork.

    This ensures the file handler is properly opened in the child worker
    process.

    Args:
        **kwargs: Celery signal arguments (unused).
    """
    setup_logging()
    logger.info("worker_logging_ready")


@worker_ready.connect
def on_worker_ready(**kwargs: object) -> None:
    """Execute once per worker after it successfully connects to the broker.

    Ensures the MinIO bucket exists before any tasks are executed.

    Args:
        **kwargs: Celery signal arguments (unused).

    Raises:
        StorageError: If bucket creation/check fails (logged but not re-raised).
    """
    from app.services.storage import StorageError, ensure_bucket_exists

    try:
        ensure_bucket_exists()
        logger.info("worker_ready", bucket_check="ok")
    except StorageError:
        logger.exception("worker_ready_bucket_failed")
