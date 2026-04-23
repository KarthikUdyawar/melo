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
def on_worker_init(**kwargs):
    """Re-run setup_logging on worker fork so file handler is open in child process."""
    setup_logging()
    logger.info("worker_logging_ready")


@worker_ready.connect
def on_worker_ready(**kwargs):
    """
    Runs once in each worker process after it connects to the broker.
    Ensures the MinIO bucket exists before any task is executed.
    """
    from app.services.storage import StorageError, ensure_bucket_exists

    try:
        ensure_bucket_exists()
        logger.info("worker_ready", bucket_check="ok")
    except StorageError:
        logger.exception("worker_ready_bucket_failed")
