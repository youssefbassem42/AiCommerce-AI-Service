import logging
from typing import Optional

from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus
from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection
from app.infrastructure.tasks.helpers import _run_async, requeue_dead_letter, update_job_progress

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.process_dead_letter_queue",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def process_dead_letter_queue_task(self, max_items: int = 50) -> dict:
    def _run():
        async def _async_run():
            collection = get_knowledge_jobs_collection()

            cursor = collection.find(
                {"status": JobStatus.DEAD_LETTER.value},
            ).sort("created_at", -1).limit(max_items)

            dead_letters = await cursor.to_list(length=max_items)
            requeued = 0

            for job in dead_letters:
                job_id_str = str(job["_id"])
                try:
                    await requeue_dead_letter(job_id_str)
                    requeued += 1
                except Exception as e:
                    logger.error("Failed to requeue dead letter %s: %s", job_id_str, e)

            return {
                "found": len(dead_letters),
                "requeued": requeued,
            }

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("process_dead_letter_queue failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
