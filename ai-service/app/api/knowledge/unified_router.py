import contextlib
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status

from app.api.auth.dependencies import (
    get_current_organization_id,
    get_current_store_id,
    get_current_user,
    get_optional_organization_id,
    get_optional_store_id,
    require_admin_role,
)
from app.api.knowledge.dependencies import (
    get_document_upload_service,
    get_knowledge_document_service,
    write_upload_temp,
)
from app.api.knowledge.generation_dependencies import (
    get_generate_handler,
    get_regenerate_handler,
)
from app.api.knowledge.generation_schemas import (
    BusinessSummaryGenerationResponseSchema,
    GenerateBusinessSummaryRequestSchema,
)
from app.api.knowledge.job_schemas import JobResponseSchema
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.knowledge.retrieval_schemas import (
    RetrievalRequestSchema,
    RetrievalResponseSchema,
    RetrievedChunkSchema,
)
from app.api.knowledge.schemas import (
    DeleteResponseSchema,
    KnowledgeDocumentResponseSchema,
    KnowledgeDocumentUpdateSchema,
    PaginatedKnowledgeDocumentResponseSchema,
    UploadResponseSchema,
)
from app.api.knowledge.unified_schemas import (
    AsyncJobAcceptedResponseSchema,
    ChunkDocumentRequestSchema,
    EmbedDocumentRequestSchema,
    ProcessDocumentRequestSchema,
)
from app.application.jobs.job_dispatcher import JobDispatcher
from app.application.knowledge.commands.generate_business_summary_command import (
    GenerateBusinessSummaryCommand,
    RegenerateBusinessSummaryCommand,
)
from app.application.knowledge.commands.generate_business_summary_handler import (
    GenerateBusinessSummaryHandler,
    RegenerateBusinessSummaryHandler,
)
from app.application.knowledge.commands.upload_command import UploadDocumentCommand
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.services import (
    DocumentUploadService,
    KnowledgeDocumentService,
)
from app.core.knowledge_settings import knowledge_settings
from app.core.path_validation import is_safe_document_path
from app.domain.auth.entities.authenticated_user import AuthenticatedUser
from app.domain.job.exceptions import JobNotFoundException
from app.domain.job.value_objects import JobType
from app.domain.knowledge.exceptions import (
    KnowledgeDocumentNotFoundException,
)
from app.infrastructure.mongodb.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=knowledge_settings.route_prefix,
    tags=["Knowledge Base"],
    dependencies=[Depends(require_admin_role)],
)


def _get_job_repository() -> JobRepository:
    return JobRepository()


def get_job_dispatcher() -> JobDispatcher:
    return JobDispatcher()


@router.post(
    "/upload",
    response_model=UploadResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to the knowledge base",
)
async def upload_document(
    file: UploadFile,
    response: Response,
    user: AuthenticatedUser = Depends(get_current_user),
    organization_id: str | None = Depends(get_optional_organization_id),
    store_id: str | None = Depends(get_optional_store_id),
    knowledge_scope: str = Query(default="general"),
    service: DocumentUploadService = Depends(get_document_upload_service),
) -> UploadResponseSchema:
    temp_path = await write_upload_temp(file)
    mime_type = file.content_type or "application/octet-stream"
    file_size = 0
    with contextlib.suppress(OSError):
        file_size = os.path.getsize(temp_path)

    command = UploadDocumentCommand(
        file_path=temp_path,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        file_size=file_size,
        uploaded_by=str(user.user_id),
        organization_id=organization_id or "default",
        store_id=store_id or "default",
        knowledge_scope=knowledge_scope,
    )
    result = await service.upload(command)
    if result.already_uploaded:
        response.status_code = status.HTTP_200_OK
    return UploadResponseSchema(**result.model_dump())


@router.get(
    "/documents",
    response_model=PaginatedKnowledgeDocumentResponseSchema,
    summary="List knowledge documents",
)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=knowledge_settings.default_page_size,
        ge=1,
        le=knowledge_settings.max_page_size,
    ),
    store_id: str = Depends(get_current_store_id),
    status_filter: str | None = Query(default=None, alias="status"),
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
) -> PaginatedKnowledgeDocumentResponseSchema:
    result = await service.list(page=page, page_size=page_size, store_id=store_id, status=status_filter)
    return PaginatedKnowledgeDocumentResponseSchema(**result.model_dump())


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponseSchema,
    summary="Get a single knowledge document by ID",
)
async def get_document(
    document_id: str,
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
    store_id: str = Depends(get_current_store_id),
) -> KnowledgeDocumentResponseSchema:
    result = await service.get_by_id(document_id, owner_store_id=store_id)
    return KnowledgeDocumentResponseSchema(**result.model_dump())


@router.put(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponseSchema,
    summary="Update a knowledge document",
)
async def update_document(
    document_id: str,
    body: KnowledgeDocumentUpdateSchema,
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
    store_id: str = Depends(get_current_store_id),
) -> KnowledgeDocumentResponseSchema:
    from app.application.knowledge.dto import KnowledgeDocumentUpdateDTO

    result = await service.update(
        document_id,
        KnowledgeDocumentUpdateDTO(**body.model_dump(exclude_unset=True)),
        owner_store_id=store_id,
    )
    return KnowledgeDocumentResponseSchema(**result.model_dump())


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponseSchema,
    summary="Delete a knowledge document (file, chunks, and linked upload)",
)
async def delete_document(
    document_id: str,
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
    store_id: str = Depends(get_current_store_id),
) -> DeleteResponseSchema:
    return DeleteResponseSchema(success=await service.delete(document_id, owner_store_id=store_id))


@router.post(
    "/process",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process a document (extract + normalize) asynchronously",
)
async def process_document(
    body: ProcessDocumentRequestSchema,
    user: AuthenticatedUser = Depends(get_current_user),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> AsyncJobAcceptedResponseSchema:
    if body.file_path and not is_safe_document_path(body.file_path):
        raise HTTPException(status_code=400, detail="Unsafe document file path rejected.")
    from app.workers.ingestion.tasks import generate_chunks_task, process_document_task

    proc_job = await dispatcher.dispatch(
        job_type=JobType.DOCUMENT_PROCESSING,
        payload=body.model_dump(),
        enqueue=lambda job_id: process_document_task.delay(
            document_id=body.document_id,
            file_path=body.file_path or "",
            mime_type=body.mime_type,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=str(user.user_id),
    )

    if body.also_chunk:
        chunk_job = await dispatcher.dispatch(
            job_type=JobType.CHUNK_GENERATION,
            payload={
                "document_id": body.document_id,
                "strategy": body.strategy,
                "chunk_size": body.chunk_size,
                "overlap": body.overlap,
                "depends_on": proc_job.id,
            },
            enqueue=lambda job_id: generate_chunks_task.delay(
                document_id=body.document_id,
                strategy=body.strategy,
                chunk_size=body.chunk_size,
                overlap=body.overlap,
                job_id=job_id,
                organization_id=organization_id,
            ),
            store_id=store_id,
            organization_id=organization_id,
            triggered_by=str(user.user_id),
        )

        return AsyncJobAcceptedResponseSchema(
            job_id=proc_job.id,
            job_type="document_processing_with_chunking",
            message=f"Processing job {proc_job.id} + chunk job {chunk_job.id} enqueued",
        )

    return AsyncJobAcceptedResponseSchema(
        job_id=proc_job.id,
        job_type="document_processing",
        message=f"Processing job {proc_job.id} enqueued",
    )


@router.post(
    "/chunk",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate chunks for a processed document",
)
async def chunk_document(
    body: ChunkDocumentRequestSchema,
    user: AuthenticatedUser = Depends(get_current_user),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> AsyncJobAcceptedResponseSchema:
    from app.workers.ingestion.tasks import generate_chunks_task

    job = await dispatcher.dispatch(
        job_type=JobType.CHUNK_GENERATION,
        payload=body.model_dump(),
        enqueue=lambda job_id: generate_chunks_task.delay(
            document_id=body.document_id,
            strategy=body.strategy,
            chunk_size=body.chunk_size,
            overlap=body.overlap,
            job_id=job_id,
            organization_id=organization_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=str(user.user_id),
    )

    return AsyncJobAcceptedResponseSchema(
        job_id=job.id,
        job_type="chunk_generation",
        message=f"Chunk job {job.id} enqueued for document {body.document_id}",
    )


@router.post(
    "/embed",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate embeddings for a document's chunks",
)
async def embed_document(
    body: EmbedDocumentRequestSchema,
    user: AuthenticatedUser = Depends(get_current_user),
    store_id: str = Depends(get_current_store_id),
    organization_id: str | None = Depends(get_optional_organization_id),
    dispatcher: JobDispatcher = Depends(get_job_dispatcher),
) -> AsyncJobAcceptedResponseSchema:
    from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository

    chunk_repo = ChunkRepository()

    chunks = await chunk_repo.find_by_document_id(body.document_id, limit=10_000)
    chunk_ids = [c.id for c in chunks]

    if not chunk_ids:
        raise KnowledgeDocumentNotFoundException(f"No chunks found for document '{body.document_id}'")

    from app.workers.embedding.tasks import generate_embeddings_task, sync_vectors_task

    embed_job = await dispatcher.dispatch(
        job_type=JobType.EMBEDDING_GENERATION,
        payload={
            "document_id": body.document_id,
            "chunk_count": len(chunk_ids),
            "model": body.model,
        },
        enqueue=lambda job_id: generate_embeddings_task.delay(
            chunk_ids=chunk_ids,
            model=body.model,
            job_id=job_id,
        ),
        store_id=store_id,
        organization_id=organization_id,
        triggered_by=str(user.user_id),
    )

    if body.sync_to_vector_store:
        sync_job = await dispatcher.dispatch(
            job_type=JobType.VECTOR_SYNC,
            payload={
                "document_id": body.document_id,
                "chunk_count": len(chunk_ids),
                "collection": body.collection_name,
                "model": body.model,
            },
            enqueue=lambda job_id: sync_vectors_task.delay(
                chunk_ids=chunk_ids,
                collection_name=body.collection_name,
                model=body.model,
                job_id=job_id,
            ),
            store_id=store_id,
            organization_id=organization_id,
            triggered_by=str(user.user_id),
        )

        return AsyncJobAcceptedResponseSchema(
            job_id=embed_job.id,
            job_type="embedding_and_vector_sync",
            message=f"Embed job {embed_job.id} + sync job {sync_job.id} enqueued for {len(chunk_ids)} chunks",
        )

    return AsyncJobAcceptedResponseSchema(
        job_id=embed_job.id,
        job_type="embedding_generation",
        message=f"Embed job {embed_job.id} enqueued for {len(chunk_ids)} chunks",
    )


@router.post(
    "/search",
    response_model=RetrievalResponseSchema,
    summary="Semantic search over knowledge base chunks",
)
async def search_knowledge(
    body: RetrievalRequestSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    from app.application.knowledge.retrieval.config import RetrievalConfig as RC
    from app.application.knowledge.retrieval.config import RetrievalFilters as RF

    config = RC(
        top_k=body.top_k,
        score_threshold=body.score_threshold,
        use_hybrid=body.use_hybrid or False,
        use_mmr=body.use_mmr,
        mmr_lambda=body.mmr_lambda,
        rerank=body.rerank,
        rerank_top_k=body.rerank_top_k,
        embedding_model=body.embedding_model,
    )
    filters = RF(
        organization_id=organization_id or body.organization_id,
        store_id=store_id,
        language=body.language,
        document_type=body.document_type,
        knowledge_scope=body.knowledge_scope,
        business_version=body.business_version,
    )
    result = await service.search(query=body.query, filters=filters, config=config)
    return RetrievalResponseSchema(
        query=result.query,
        results=[RetrievedChunkSchema(**dto.model_dump()) for dto in result.results],
        total_count=result.total_count,
        strategy=result.strategy,
        latency_ms=result.latency_ms,
        filters_applied=result.filters_applied,
    )


@router.post(
    "/search/hybrid",
    response_model=RetrievalResponseSchema,
    summary="Hybrid search (vector + keyword) over knowledge base chunks",
)
async def hybrid_search_knowledge(
    body: RetrievalRequestSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    from app.application.knowledge.retrieval.config import RetrievalConfig as RC
    from app.application.knowledge.retrieval.config import RetrievalFilters as RF

    config = RC(
        top_k=body.top_k,
        score_threshold=body.score_threshold,
        use_hybrid=True,
        use_mmr=body.use_mmr,
        mmr_lambda=body.mmr_lambda,
        rerank=body.rerank,
        rerank_top_k=body.rerank_top_k,
        embedding_model=body.embedding_model,
    )
    filters = RF(
        organization_id=organization_id or body.organization_id,
        store_id=store_id,
        language=body.language,
        document_type=body.document_type,
        knowledge_scope=body.knowledge_scope,
        business_version=body.business_version,
    )
    result = await service.search(query=body.query, filters=filters, config=config)
    return RetrievalResponseSchema(
        query=result.query,
        results=[RetrievedChunkSchema(**dto.model_dump()) for dto in result.results],
        total_count=result.total_count,
        strategy=result.strategy,
        latency_ms=result.latency_ms,
        filters_applied=result.filters_applied,
    )


@router.post(
    "/summary",
    response_model=BusinessSummaryGenerationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a business summary for a store",
)
async def generate_summary(
    store_id: str = Depends(get_current_store_id),
    body: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    handler: GenerateBusinessSummaryHandler = Depends(get_generate_handler),
) -> BusinessSummaryGenerationResponseSchema:
    gen_config = GenerationConfig()
    if body.model:
        gen_config.model = body.model
    if body.temperature is not None:
        gen_config.temperature = body.temperature
    if body.max_tokens is not None:
        gen_config.max_tokens = body.max_tokens
    command = GenerateBusinessSummaryCommand(
        store_id=store_id,
        config=gen_config,
    )
    result = await handler.handle(command)
    return BusinessSummaryGenerationResponseSchema(**result.model_dump())


@router.post(
    "/summary/regenerate",
    response_model=BusinessSummaryGenerationResponseSchema,
    summary="Regenerate the business summary for a store",
)
async def regenerate_summary(
    store_id: str = Depends(get_current_store_id),
    body: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    handler: RegenerateBusinessSummaryHandler = Depends(get_regenerate_handler),
) -> BusinessSummaryGenerationResponseSchema:
    gen_config = GenerationConfig()
    if body.model:
        gen_config.model = body.model
    if body.temperature is not None:
        gen_config.temperature = body.temperature
    if body.max_tokens is not None:
        gen_config.max_tokens = body.max_tokens
    command = RegenerateBusinessSummaryCommand(
        store_id=store_id,
        config=gen_config,
    )
    result = await handler.handle(command)
    return BusinessSummaryGenerationResponseSchema(**result.model_dump())


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponseSchema,
    summary="Get the status of an async knowledge job",
)
async def get_job_status(
    job_id: str,
    store_id: str = Depends(get_current_store_id),
    repo: JobRepository = Depends(_get_job_repository),
) -> JobResponseSchema:
    job = await repo.find_by_id(job_id)
    if not job or (job.store_id and job.store_id != store_id):
        raise JobNotFoundException(f"Job '{job_id}' not found")
    return JobResponseSchema(
        id=job.id,
        job_type=job.job_type.value if hasattr(job.job_type, "value") else str(job.job_type),
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
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
