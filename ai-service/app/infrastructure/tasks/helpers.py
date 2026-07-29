import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine, Optional

from bson import ObjectId

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection

logger = logging.getLogger(__name__)


def _run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


async def create_job(
    job_type: JobType,
    payload: dict[str, Any],
    store_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
    max_retries: int = 3,
) -> KnowledgeJob:
    collection = get_knowledge_jobs_collection()
    job_id = str(ObjectId())
    doc = {
        "_id": ObjectId(job_id),
        "job_type": job_type.value,
        "status": JobStatus.PENDING.value,
        "progress": 0.0,
        "payload": payload,
        "result": None,
        "error_message": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "store_id": store_id,
        "organization_id": organization_id,
        "triggered_by": triggered_by,
        "celery_task_id": None,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    await collection.insert_one(doc)
    entity = KnowledgeJob(
        id=job_id,
        job_type=job_type,
        status=JobStatus.PENDING,
        payload=payload,
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
        max_retries=max_retries,
    )
    logger.info("Created job %s [%s] payload=%s", job_id, job_type.value, payload)
    return entity


async def update_job_progress(
    job_id: str,
    progress: float,
    status: Optional[JobStatus] = None,
) -> None:
    collection = get_knowledge_jobs_collection()
    update: dict[str, Any] = {
        "$set": {
            "progress": progress,
            "updated_at": datetime.now(UTC),
        }
    }
    if status:
        update["$set"]["status"] = status.value
        if status == JobStatus.RUNNING:
            update["$set"]["started_at"] = datetime.now(UTC)
    await collection.update_one({"_id": ObjectId(job_id)}, update)


async def complete_job(
    job_id: str,
    result: Optional[dict[str, Any]] = None,
    celery_task_id: Optional[str] = None,
) -> None:
    collection = get_knowledge_jobs_collection()
    update: dict[str, Any] = {
        "$set": {
            "status": JobStatus.COMPLETED.value,
            "progress": 1.0,
            "result": result or {},
            "completed_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }
    }
    if celery_task_id:
        update["$set"]["celery_task_id"] = celery_task_id
    await collection.update_one({"_id": ObjectId(job_id)}, update)


async def fail_job(
    job_id: str,
    error_message: str,
    retry_count: int,
    max_retries: int,
) -> JobStatus:
    collection = get_knowledge_jobs_collection()
    now = datetime.now(UTC)

    if retry_count >= max_retries:
        target_status = JobStatus.DEAD_LETTER
    else:
        target_status = JobStatus.RETRYING

    await collection.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": target_status.value,
                "error_message": error_message,
                "retry_count": retry_count,
                "completed_at": now,
                "updated_at": now,
            }
        },
    )
    logger.warning(
        "Job %s -> %s (retry %d/%d): %s",
        job_id, target_status.value, retry_count, max_retries, error_message,
    )
    return target_status


async def set_celery_task_id(job_id: str, task_id: str) -> None:
    collection = get_knowledge_jobs_collection()
    await collection.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"celery_task_id": task_id, "updated_at": datetime.now(UTC)}},
    )


async def requeue_dead_letter(job_id: str) -> None:
    collection = get_knowledge_jobs_collection()
    await collection.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": JobStatus.PENDING.value,
                "error_message": None,
                "retry_count": 0,
                "completed_at": None,
                "updated_at": datetime.now(UTC),
            }
        },
    )
    logger.info("Requeued dead letter job %s", job_id)
