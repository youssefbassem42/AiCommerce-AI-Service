from collections.abc import Callable
from typing import Any

from app.core.exceptions import TaskQueueUnavailableException
from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection
from app.infrastructure.tasks.helpers import create_job, set_celery_task_id


class JobDispatcher:
    """Creates a job record, enqueues its Celery task, and links them.

    Single home for the job lifecycle used by request handlers. Keeps routers
    thin and is async-correct: the celery task id is linked with await, never
    through asyncio.run() inside a running event loop.
    """

    async def dispatch(
        self,
        job_type: JobType,
        payload: dict[str, Any],
        enqueue: Callable[[str], Any],
        store_id: str | None = None,
        organization_id: str | None = None,
        triggered_by: str | None = None,
        max_retries: int = 3,
    ) -> KnowledgeJob:
        from datetime import UTC, datetime

        from bson import ObjectId

        job = await create_job(
            job_type=job_type,
            payload=payload,
            store_id=store_id,
            organization_id=organization_id,
            triggered_by=triggered_by,
            max_retries=max_retries,
        )
        try:
            task = enqueue(job.id)
        except Exception as exc:  # broker down / misconfigured broker URL
            await get_knowledge_jobs_collection().update_one(
                {"_id": ObjectId(job.id)},
                {
                    "$set": {
                        "status": JobStatus.FAILED.value,
                        "error_message": f"Failed to enqueue {job_type.value}: {exc}",
                        "completed_at": datetime.now(UTC),
                        "updated_at": datetime.now(UTC),
                    }
                },
            )
            raise TaskQueueUnavailableException(
                "The async task queue is currently unavailable. Confirm the Celery "
                "worker and broker (Redis) are running and REDIS_URL is reachable, "
                f"then retry. (job {job.id} marked failed.)"
            ) from exc
        await set_celery_task_id(job.id, task.id)
        return job
