# app/workers/celery_app.py
import logging
import os

from celery import Celery
from celery.signals import worker_ready

logger = logging.getLogger(__name__)

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


@worker_ready.connect
def on_worker_ready(**kwargs):
    """
    Runs once in each worker process after it connects to the broker.
    Ensures the MinIO bucket exists before any task is executed.
    """
    from app.services.storage import StorageError, ensure_bucket_exists

    try:
        ensure_bucket_exists()
    except StorageError:
        logger.exception("Failed to ensure MinIO bucket on worker startup")
