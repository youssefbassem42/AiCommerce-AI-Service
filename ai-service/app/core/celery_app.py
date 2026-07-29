from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "ai_commerce_tasks",
    broker=settings.REDIS_SETTINGS.REDIS_URL,
    backend=settings.REDIS_SETTINGS.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=3600,
    task_time_limit=3900,
    result_expires=86400,
    imports=[
        "app.infrastructure.tasks.celery_tasks",
        "app.workers.ingestion.tasks",
        "app.workers.summarization.tasks",
        "app.workers.embedding.tasks",
        "app.workers.scheduler.tasks",
        "app.workers.cleanup.tasks",
    ],
)

celery_app.conf.task_routes = {
    "knowledge.*": {"queue": "ingestion"},
    "kb.extract_document": {"queue": "ingestion"},
    "kb.chunk_document": {"queue": "ingestion"},
    "kb.embed_chunks": {"queue": "embedding"},
    "kb.sync_vector_db": {"queue": "embedding"},
    "kb.generate_summary": {"queue": "summarization"},
    "kb.bump_version": {"queue": "default"},
    "knowledge.retry_failed_jobs": {"queue": "scheduler"},
    "knowledge.cleanup_dead_letters": {"queue": "scheduler"},
    "knowledge.process_dead_letter_queue": {"queue": "cleanup"},
    "ai.*": {"queue": "default"},
}

celery_app.conf.task_default_queue = "default"

celery_app.conf.beat_schedule = {
    "retry-failed-jobs-every-15m": {
        "task": "knowledge.retry_failed_jobs",
        "schedule": crontab(minute="*/15"),
    },
    "cleanup-dead-letters-daily": {
        "task": "knowledge.cleanup_dead_letters",
        "schedule": crontab(hour=3, minute=0),
        "kwargs": {"dry_run": False},
    },
}
