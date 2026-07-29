import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from app.api.knowledge.dependencies import (
    get_business_summary_service,
    get_document_upload_service,
    get_knowledge_chunk_service,
    get_knowledge_document_service,
    get_upload_repository,
    write_upload_temp,
)
from app.api.knowledge.generation_dependencies import (
    get_generate_handler,
    get_list_history_handler,
    get_regenerate_handler,
)
from app.api.knowledge.generation_schemas import (
    BusinessSummaryGenerationResponseSchema,
    GenerateBusinessSummaryRequestSchema,
    PaginatedBusinessSummaryHistoryResponseSchema,
)
from app.api.knowledge.job_schemas import JobResponseSchema
from app.api.knowledge.retrieval_schemas import (
    RetrievalRequestSchema,
    RetrievalResponseSchema,
    RetrievedChunkSchema,
)
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.knowledge.schemas import (
    DeleteResponseSchema,
    KnowledgeChunkResponseSchema,
    KnowledgeDocumentCreateSchema,
    KnowledgeDocumentResponseSchema,
    KnowledgeDocumentUpdateSchema,
    PaginatedKnowledgeChunkResponseSchema,
    PaginatedKnowledgeDocumentResponseSchema,
    PaginatedUploadResponseSchema,
    UploadResponseSchema,
)
from app.api.knowledge.unified_schemas import (
    AsyncJobAcceptedResponseSchema,
    ChunkDocumentRequestSchema,
    EmbedDocumentRequestSchema,
    ProcessDocumentRequestSchema,
)
from app.application.knowledge.commands.generate_business_summary_command import (
    GenerateBusinessSummaryCommand,
    RegenerateBusinessSummaryCommand,
)
from app.application.knowledge.commands.generate_business_summary_handler import (
    GenerateBusinessSummaryHandler,
    RegenerateBusinessSummaryHandler,
)
from app.application.knowledge.generation.config import GenerationConfig
from app.application.knowledge.commands.upload_command import UploadDocumentCommand
from app.application.knowledge.queries.list_business_summary_history_handler import (
    ListBusinessSummaryHistoryHandler,
)
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.services import (
    BusinessSummaryService,
    DocumentUploadService,
    KnowledgeChunkService,
    KnowledgeDocumentService,
)
from app.core.knowledge_settings import knowledge_settings
from app.domain.job.exceptions import JobNotFoundException
from app.domain.job.repositories.job_repository import JobRepository
from app.domain.job.value_objects import JobStatus
from app.domain.knowledge.exceptions import (
    BusinessSummaryNotFoundException,
    DuplicateUploadException,
    FileValidationException,
    KnowledgeChunkNotFoundException,
    KnowledgeDocumentNotFoundException,
    KnowledgeDomainException,
)
from app.infrastructure.mongodb.repositories.job_repository import JobRepository
from app.infrastructure.mongodb.repositories.upload_repository import UploadRepository
from app.infrastructure.tasks.helpers import _run_async, create_job, set_celery_task_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix=knowledge_settings.route_prefix, tags=["Knowledge Base"])


def _handle_exception(exc: Exception) -> None:
    if isinstance(
        exc,
        (
            KnowledgeDocumentNotFoundException,
            KnowledgeChunkNotFoundException,
            BusinessSummaryNotFoundException,
            JobNotFoundException,
        ),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (FileValidationException, DuplicateUploadException)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, KnowledgeDomainException):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


def _get_job_repository() -> JobRepository:
    return JobRepository()


@router.post(
    "/upload",
    response_model=UploadResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to the knowledge base",
)
async def upload_document(
    file: UploadFile,
    uploaded_by: str = Query(...),
    organization_id: str = Query(...),
    store_id: str = Query(...),
    knowledge_scope: str = Query(default="general"),
    service: DocumentUploadService = Depends(get_document_upload_service),
) -> UploadResponseSchema:
    try:
        temp_path = await write_upload_temp(file)
        mime_type = file.content_type or "application/octet-stream"
        file_size = 0
        try:
            file_size = os.path.getsize(temp_path)
        except OSError:
            pass

        command = UploadDocumentCommand(
            file_path=temp_path,
            original_filename=file.filename or "upload",
            mime_type=mime_type,
            file_size=file_size,
            uploaded_by=uploaded_by,
            organization_id=organization_id,
            store_id=store_id,
            knowledge_scope=knowledge_scope,
        )
        result = await service.upload(command)
        return UploadResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


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
    store_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
) -> PaginatedKnowledgeDocumentResponseSchema:
    try:
        result = await service.list(
            page=page, page_size=page_size, store_id=store_id, status=status_filter
        )
        return PaginatedKnowledgeDocumentResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponseSchema,
    summary="Get a single knowledge document by ID",
)
async def get_document(
    document_id: str,
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
) -> KnowledgeDocumentResponseSchema:
    try:
        result = await service.get_by_id(document_id)
        return KnowledgeDocumentResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponseSchema,
    summary="Delete a knowledge document",
)
async def delete_document(
    document_id: str,
    service: KnowledgeDocumentService = Depends(get_knowledge_document_service),
) -> DeleteResponseSchema:
    try:
        return DeleteResponseSchema(success=await service.delete(document_id))
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/process",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Process a document (extract + normalize) asynchronously",
)
async def process_document(
    body: ProcessDocumentRequestSchema,
) -> AsyncJobAcceptedResponseSchema:
    try:
        from app.workers.ingestion.tasks import generate_chunks_task, process_document_task

        proc_job = await create_job(
            job_type="document_processing",
            payload=body.model_dump(),
            store_id=body.store_id,
            organization_id=body.organization_id,
            triggered_by=body.triggered_by,
        )
        proc_task = process_document_task.delay(
            document_id=body.document_id,
            file_path=body.file_path,
            mime_type=body.mime_type,
            job_id=proc_job.id,
        )
        _run_async(set_celery_task_id(proc_job.id, proc_task.id))

        if body.also_chunk:
            chunk_job = await create_job(
                job_type="chunk_generation",
                payload={
                    "document_id": body.document_id,
                    "strategy": body.strategy,
                    "chunk_size": body.chunk_size,
                    "overlap": body.overlap,
                    "depends_on": proc_job.id,
                },
                store_id=body.store_id,
                organization_id=body.organization_id,
                triggered_by=body.triggered_by,
            )
            chunk_task = generate_chunks_task.delay(
                document_id=body.document_id,
                strategy=body.strategy,
                chunk_size=body.chunk_size,
                overlap=body.overlap,
                job_id=chunk_job.id,
            )
            _run_async(set_celery_task_id(chunk_job.id, chunk_task.id))

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
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/chunk",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate chunks for a processed document",
)
async def chunk_document(
    body: ChunkDocumentRequestSchema,
) -> AsyncJobAcceptedResponseSchema:
    try:
        from app.workers.ingestion.tasks import generate_chunks_task

        job = await create_job(
            job_type="chunk_generation",
            payload=body.model_dump(),
            store_id=body.store_id,
            organization_id=body.organization_id,
            triggered_by=body.triggered_by,
        )
        task = generate_chunks_task.delay(
            document_id=body.document_id,
            strategy=body.strategy,
            chunk_size=body.chunk_size,
            overlap=body.overlap,
            job_id=job.id,
        )
        _run_async(set_celery_task_id(job.id, task.id))

        return AsyncJobAcceptedResponseSchema(
            job_id=job.id,
            job_type="chunk_generation",
            message=f"Chunk job {job.id} enqueued for document {body.document_id}",
        )
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/embed",
    response_model=AsyncJobAcceptedResponseSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate embeddings for a document's chunks",
)
async def embed_document(
    body: EmbedDocumentRequestSchema,
) -> AsyncJobAcceptedResponseSchema:
    try:
        from app.application.knowledge.services import KnowledgeChunkService
        from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository

        chunk_repo = ChunkRepository()
        chunk_service = KnowledgeChunkService(repository=chunk_repo)

        chunks = await chunk_repo.find_by_document_id(body.document_id, limit=10_000)
        chunk_ids = [c.id for c in chunks]

        if not chunk_ids:
            raise KnowledgeDocumentNotFoundException(
                f"No chunks found for document '{body.document_id}'"
            )

        from app.workers.embedding.tasks import generate_embeddings_task, sync_vectors_task

        embed_job = await create_job(
            job_type="embedding_generation",
            payload={
                "document_id": body.document_id,
                "chunk_count": len(chunk_ids),
                "model": body.model,
            },
            store_id=body.store_id,
            organization_id=body.organization_id,
            triggered_by=body.triggered_by,
        )
        embed_task = generate_embeddings_task.delay(
            chunk_ids=chunk_ids,
            model=body.model,
            job_id=embed_job.id,
        )
        _run_async(set_celery_task_id(embed_job.id, embed_task.id))

        if body.sync_to_vector_store:
            sync_job = await create_job(
                job_type="vector_sync",
                payload={
                    "document_id": body.document_id,
                    "chunk_count": len(chunk_ids),
                    "collection": body.collection_name,
                    "model": body.model,
                },
                store_id=body.store_id,
                organization_id=body.organization_id,
                triggered_by=body.triggered_by,
            )
            sync_task = sync_vectors_task.delay(
                chunk_ids=chunk_ids,
                collection_name=body.collection_name,
                model=body.model,
                job_id=sync_job.id,
            )
            _run_async(set_celery_task_id(sync_job.id, sync_task.id))

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
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/search",
    response_model=RetrievalResponseSchema,
    summary="Semantic search over knowledge base chunks",
)
async def search_knowledge(
    body: RetrievalRequestSchema,
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    try:
        from app.application.knowledge.retrieval.config import RetrievalConfig as RC, RetrievalFilters as RF

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
            organization_id=body.organization_id,
            store_id=body.store_id,
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
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/search/hybrid",
    response_model=RetrievalResponseSchema,
    summary="Hybrid search (vector + keyword) over knowledge base chunks",
)
async def hybrid_search_knowledge(
    body: RetrievalRequestSchema,
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    try:
        from app.application.knowledge.retrieval.config import RetrievalConfig as RC, RetrievalFilters as RF

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
            organization_id=body.organization_id,
            store_id=body.store_id,
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
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/summary",
    response_model=BusinessSummaryGenerationResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a business summary for a store",
)
async def generate_summary(
    store_id: str = Query(...),
    body: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    handler: GenerateBusinessSummaryHandler = Depends(get_generate_handler),
) -> BusinessSummaryGenerationResponseSchema:
    try:
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
    except Exception as exc:
        _handle_exception(exc)


@router.post(
    "/summary/regenerate",
    response_model=BusinessSummaryGenerationResponseSchema,
    summary="Regenerate the business summary for a store",
)
async def regenerate_summary(
    store_id: str = Query(...),
    body: GenerateBusinessSummaryRequestSchema = Depends(lambda: GenerateBusinessSummaryRequestSchema()),
    handler: RegenerateBusinessSummaryHandler = Depends(get_regenerate_handler),
) -> BusinessSummaryGenerationResponseSchema:
    try:
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
    except Exception as exc:
        _handle_exception(exc)


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponseSchema,
    summary="Get the status of an async knowledge job",
)
async def get_job_status(
    job_id: str,
    repo: JobRepository = Depends(_get_job_repository),
) -> JobResponseSchema:
    try:
        job = await repo.find_by_id(job_id)
        if not job:
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
    except JobNotFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job '{job_id}' not found")
    except Exception as exc:
        _handle_exception(exc)
