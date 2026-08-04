from collections.abc import Callable
from typing import Any

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobType
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
        job = await create_job(
            job_type=job_type,
            payload=payload,
            store_id=store_id,
            organization_id=organization_id,
            triggered_by=triggered_by,
            max_retries=max_retries,
        )
        task = enqueue(job.id)
        await set_celery_task_id(job.id, task.id)
        return job
