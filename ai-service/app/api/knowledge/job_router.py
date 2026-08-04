import logging

from fastapi import APIRouter, Depends, Query, status

from app.api.knowledge.job_schemas import JobCreateResponseSchema, JobResponseSchema, PaginatedJobResponseSchema
from app.application.jobs.job_dispatcher import JobDispatcher
from app.domain.job.exceptions import JobNotFoundException
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.repositories.job_repository import JobRepository
from app.infrastructure.tasks.helpers import requeue_dead_letter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge/jobs", tags=["Knowledge Jobs"])


def get_job_repository() -> JobRepository:
    return JobRepository()


def get_job_dispatcher() -> JobDispatcher:
    return JobDispatcher()


@router.post("/document-processing", response_model=JobCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_document_processing_job(
    document_id: str = Query(...),
    file_path: str = Query(...),
    mime_type: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    triggered_by: str | None = Query(default=None),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobCreateResponseSchema:
    from app.workers.ingestion.tasks import process_document_task

    job = await dispatcher.dispatch(
        job_type=JobType.DOCUMENT_PROCESSING,
        payload={
            "document_id": document_id,
            "file_path": file_path,
            "mime_type": mime_type,
        },
        enqueue=lambda job_id: process_document_task.delay(
            document_id=document_id,
            file_path=file_path,
            mime_type=mime_type,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
    )
    return JobCreateResponseSchema(
        job_id=job.id,
        job_type=JobType.DOCUMENT_PROCESSING.value,
        status=JobStatus.PENDING.value,
        message="Document processing job enqueued",
    )


@router.post("/chunk-generation", response_model=JobCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_chunk_generation_job(
    document_id: str = Query(...),
    strategy: str = Query(default="recursive_character"),
    chunk_size: int = Query(default=1000, ge=100, le=5000),
    overlap: int = Query(default=200, ge=0, le=1000),
    store_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    triggered_by: str | None = Query(default=None),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobCreateResponseSchema:
    from app.workers.ingestion.tasks import generate_chunks_task

    job = await dispatcher.dispatch(
        job_type=JobType.CHUNK_GENERATION,
        payload={
            "document_id": document_id,
            "strategy": strategy,
            "chunk_size": chunk_size,
            "overlap": overlap,
        },
        enqueue=lambda job_id: generate_chunks_task.delay(
            document_id=document_id,
            strategy=strategy,
            chunk_size=chunk_size,
            overlap=overlap,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
    )
    return JobCreateResponseSchema(
        job_id=job.id,
        job_type=JobType.CHUNK_GENERATION.value,
        status=JobStatus.PENDING.value,
        message="Chunk generation job enqueued",
    )


@router.post("/summary-generation", response_model=JobCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_summary_generation_job(
    store_id: str = Query(...),
    model: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    triggered_by: str | None = Query(default=None),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobCreateResponseSchema:
    from app.workers.summarization.tasks import generate_summary_task

    job = await dispatcher.dispatch(
        job_type=JobType.SUMMARY_GENERATION,
        payload={
            "store_id": store_id,
            "model": model or "gpt-4o-mini",
        },
        enqueue=lambda job_id: generate_summary_task.delay(
            store_id=store_id,
            model=model,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
    )
    return JobCreateResponseSchema(
        job_id=job.id,
        job_type=JobType.SUMMARY_GENERATION.value,
        status=JobStatus.PENDING.value,
        message="Summary generation job enqueued",
    )


@router.post("/embedding-generation", response_model=JobCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_embedding_generation_job(
    chunk_ids: list[str] = Query(...),
    model: str = Query(default="gemini-embedding-001"),
    store_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    triggered_by: str | None = Query(default=None),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobCreateResponseSchema:
    from app.workers.embedding.tasks import generate_embeddings_task

    job = await dispatcher.dispatch(
        job_type=JobType.EMBEDDING_GENERATION,
        payload={
            "chunk_count": len(chunk_ids),
            "model": model,
        },
        enqueue=lambda job_id: generate_embeddings_task.delay(
            chunk_ids=chunk_ids,
            model=model,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
    )
    return JobCreateResponseSchema(
        job_id=job.id,
        job_type=JobType.EMBEDDING_GENERATION.value,
        status=JobStatus.PENDING.value,
        message="Embedding generation job enqueued",
    )


@router.post("/vector-sync", response_model=JobCreateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_vector_sync_job(
    chunk_ids: list[str] = Query(...),
    collection_name: str = Query(default="kb_default"),
    model: str = Query(default="gemini-embedding-001"),
    store_id: str | None = Query(default=None),
    organization_id: str | None = Query(default=None),
    triggered_by: str | None = Query(default=None),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> JobCreateResponseSchema:
    from app.workers.embedding.tasks import sync_vectors_task

    job = await dispatcher.dispatch(
        job_type=JobType.VECTOR_SYNC,
        payload={
            "chunk_count": len(chunk_ids),
            "collection": collection_name,
            "model": model,
        },
        enqueue=lambda job_id: sync_vectors_task.delay(
            chunk_ids=chunk_ids,
            collection_name=collection_name,
            model=model,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=triggered_by,
    )
    return JobCreateResponseSchema(
        job_id=job.id,
        job_type=JobType.VECTOR_SYNC.value,
        status=JobStatus.PENDING.value,
        message="Vector sync job enqueued",
    )


@router.get("/{job_id}", response_model=JobResponseSchema)
async def get_job_status(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
) -> JobResponseSchema:
    job = await repo.find_by_id(job_id)
    if not job:
        raise JobNotFoundException(f"Job '{job_id}' not found")
    return JobResponseSchema(
        id=job.id,
        job_type=job.job_type.value,
        status=job.status.value,
        progress=job.progress,
        payload=job.payload,
        result=job.result,
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        store_id=job.store_id,
        organization_id=job.organization_id,
        triggered_by=job.triggered_by,
        celery_task_id=job.celery_task_id,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=PaginatedJobResponseSchema)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    job_type: str | None = Query(default=None),
    store_id: str | None = Query(default=None),
    repo: JobRepository = Depends(get_job_repository),
) -> PaginatedJobResponseSchema:
    filters: dict = {}
    if status_filter:
        filters["status"] = status_filter
    if job_type:
        filters["job_type"] = job_type
    if store_id:
        filters["store_id"] = store_id

    items, total = await repo.paginate(filters, page=page, page_size=page_size)
    return PaginatedJobResponseSchema(
        items=[
            JobResponseSchema(
                id=j.id,
                job_type=j.job_type.value,
                status=j.status.value,
                progress=j.progress,
                payload=j.payload,
                result=j.result,
                error_message=j.error_message,
                retry_count=j.retry_count,
                max_retries=j.max_retries,
                store_id=j.store_id,
                organization_id=j.organization_id,
                triggered_by=j.triggered_by,
                celery_task_id=j.celery_task_id,
                started_at=j.started_at,
                completed_at=j.completed_at,
                created_at=j.created_at,
                updated_at=j.updated_at,
            )
            for j in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{job_id}/requeue", response_model=JobResponseSchema)
async def requeue_job(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
) -> JobResponseSchema:
    job = await repo.find_by_id(job_id)
    if not job:
        raise JobNotFoundException(f"Job '{job_id}' not found")

    await requeue_dead_letter(job_id)
    updated = await repo.find_by_id(job_id)
    if not updated:
        raise JobNotFoundException(f"Job '{job_id}' not found after requeue")

    return JobResponseSchema(
        id=updated.id,
        job_type=updated.job_type.value,
        status=updated.status.value,
        progress=updated.progress,
        payload=updated.payload,
        result=updated.result,
        error_message=updated.error_message,
        retry_count=updated.retry_count,
        max_retries=updated.max_retries,
        store_id=updated.store_id,
        organization_id=updated.organization_id,
        triggered_by=updated.triggered_by,
        celery_task_id=updated.celery_task_id,
        started_at=updated.started_at,
        completed_at=updated.completed_at,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )
