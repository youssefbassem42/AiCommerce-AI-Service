import logging
from datetime import UTC, datetime, timedelta

from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection
from app.infrastructure.tasks.helpers import _run_async, requeue_dead_letter

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.retry_failed_jobs",
    max_retries=1,
    acks_late=True,
)
def retry_failed_jobs_task() -> dict:
    def _run():
        async def _async_run():
            collection = get_knowledge_jobs_collection()

            stale_running = await collection.find({
                "status": JobStatus.RUNNING.value,
                "started_at": {"$lt": datetime.now(UTC) - timedelta(hours=2)},
            }).to_list(length=100)

            requeued_running = 0
            for job in stale_running:
                await collection.update_one(
                    {"_id": job["_id"]},
                    {
                        "$set": {
                            "status": JobStatus.RETRYING.value,
                            "error_message": "Stale job timed out after 2 hours",
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
                requeued_running += 1

            retryable = await collection.find({
                "status": JobStatus.RETRYING.value,
                "retry_count": {"$lt": 3},
            }).to_list(length=100)

            requeued_retries = 0
            for job in retryable:
                await collection.update_one(
                    {"_id": job["_id"]},
                    {
                        "$set": {
                            "status": JobStatus.PENDING.value,
                            "updated_at": datetime.now(UTC),
                        }
                    },
                )
                requeued_retries += 1

            return {
                "stale_running_requeued": requeued_running,
                "retryable_requeued": requeued_retries,
            }

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("retry_failed_jobs failed: %s", exc, exc_info=True)
        return {"error": str(exc)}


@celery_app.task(
    name="knowledge.cleanup_dead_letters",
    max_retries=1,
    acks_late=True,
)
def cleanup_dead_letters_task(dry_run: bool = True) -> dict:
    def _run():
        async def _async_run():
            collection = get_knowledge_jobs_collection()

            cutoff = datetime.now(UTC) - timedelta(days=7)
            old_dead = await collection.find({
                "status": JobStatus.DEAD_LETTER.value,
                "completed_at": {"$lt": cutoff},
            }).to_list(length=200)

            if not dry_run:
                ids = [j["_id"] for j in old_dead]
                if ids:
                    await collection.delete_many({"_id": {"$in": ids}})

            return {
                "found_old_dead_letters": len(old_dead),
                "dry_run": dry_run,
                "deleted": 0 if dry_run else len(old_dead),
            }

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        logger.error("cleanup_dead_letters failed: %s", exc, exc_info=True)
        return {"error": str(exc)}
