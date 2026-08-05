import logging
import time

from app.application.knowledge.chunking.chunking_service import ChunkingConfig, ChunkingService
from app.application.knowledge.processing.pipeline import ProcessingPipeline
from app.application.knowledge.processing.processor import DocumentProcessor
from app.core.celery_app import celery_app
from app.core.path_validation import is_safe_document_path
from app.domain.job.value_objects import JobStatus
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.knowledge.extractors import ExtractorFactory
from app.infrastructure.mongodb.collections import get_knowledge_versions_collection
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.tasks.helpers import _run_async, complete_job, fail_job, update_job_progress

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_document_task(
    self, document_id: str, file_path: str, mime_type: str | None = None, job_id: str | None = None
) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.1, JobStatus.RUNNING)

            repo = KnowledgeRepository()
            extractor_factory = ExtractorFactory()
            pipeline = ProcessingPipeline()
            processor = DocumentProcessor(repo, extractor_factory, pipeline)

            if not is_safe_document_path(file_path):
                raise ValueError(f"Unsafe document file path rejected: {file_path!r}")

            doc = await repo.find_by_id(document_id)
            if not doc:
                raise ValueError(f"Document '{document_id}' not found")

            if job_id:
                await update_job_progress(job_id, 0.3)

            updated = await processor.process(doc, file_path, mime_type)

            if job_id:
                await update_job_progress(job_id, 1.0)

            result = {
                "document_id": updated.id,
                "status": updated.status,
                "word_count": updated.word_count,
                "char_count": updated.char_count,
                "estimated_tokens": updated.estimated_tokens,
                "language": updated.language,
            }

            if job_id:
                await complete_job(job_id, result)

            return result

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        if job_id:
            _run_async(fail_job(job_id, str(exc), self.request.retries, self.max_retries))
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)


@celery_app.task(name="kb.extract_document", bind=True, max_retries=3, default_retry_delay=30)
def extract_document_task(self, doc_id: str, file_path: str, org_id: str, store_id: str) -> bool:  # noqa: ARG001
    """Extract text from a document file in the background."""

    async def _run() -> bool:
        TenantContext(organization_id=org_id, store_id=store_id)
        if not is_safe_document_path(file_path):
            logger.warning("extract_document_task: unsafe file path rejected: %r", file_path)
            return False
        repo = KnowledgeRepository()
        doc = await repo.find_by_id(doc_id)
        if not doc:
            logger.warning("extract_document_task: document '%s' not found", doc_id)
            return False
        processor = _build_processor(repo)
        await processor.process(doc, file_path)
        return True

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("extract_document_task failed for doc '%s': %s", doc_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="kb.chunk_document", bind=True, max_retries=3, default_retry_delay=30)
def chunk_document_task(self, doc_id: str, config_dict: dict, org_id: str, store_id: str) -> int:  # noqa: ARG001
    """Chunk a processed document in the background."""

    async def _run() -> int:
        repo = KnowledgeRepository()
        doc = await repo.find_by_id(doc_id)
        if not doc:
            logger.warning("chunk_document_task: document '%s' not found", doc_id)
            return 0
        config = ChunkingConfig(**config_dict)
        chunk_repo = ChunkRepository()
        service = ChunkingService(chunk_repository=chunk_repo, knowledge_repository=repo)
        result = await service.chunk_document(doc, config)
        logger.info("Chunked doc '%s': %d chunks", doc_id, result.chunk_count)
        return result.chunk_count

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("chunk_document_task failed for doc '%s': %s", doc_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="kb.bump_version", bind=True)
def bump_version_task(self, store_id: str, version: int, org_id: str, store_slug: str) -> bool:  # noqa: ARG001
    """Finalize the knowledge version for a store."""

    async def _run() -> bool:
        col = get_knowledge_versions_collection()
        result = await col.update_one(
            {
                "organization_id": org_id,
                "store_id": store_id,
                "version_number": version,
            },
            {"$set": {"completed_at": time.time(), "status": "active"}},
        )
        logger.info(
            "Knowledge version v%d %s for store '%s'",
            version,
            "finalized" if result.modified_count else "not found",
            store_id,
        )
        return result.modified_count > 0

    return _run_async(_run())


def _build_processor(repo: KnowledgeRepository) -> DocumentProcessor:
    return DocumentProcessor(
        repository=repo,
        extractor_factory=ExtractorFactory(),
        pipeline=ProcessingPipeline(),
    )


@celery_app.task(
    name="knowledge.generate_chunks",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def generate_chunks_task(
    self,
    document_id: str,
    strategy: str = "recursive_character",
    chunk_size: int = 1000,
    overlap: int = 200,
    job_id: str | None = None,
) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.1, JobStatus.RUNNING)

            chunk_repo = ChunkRepository()
            knowledge_repo = KnowledgeRepository()
            service = ChunkingService(chunk_repo, knowledge_repo)

            doc = await knowledge_repo.find_by_id(document_id)
            if not doc:
                raise ValueError(f"Document '{document_id}' not found")

            if job_id:
                await update_job_progress(job_id, 0.3)

            config = ChunkingConfig(strategy=strategy, chunk_size=chunk_size, overlap=overlap)
            result = await service.chunk_document(doc, config)

            if job_id:
                await update_job_progress(job_id, 1.0)

            output = {
                "document_id": result.document_id,
                "strategy": result.strategy,
                "chunk_count": result.chunk_count,
                "chunk_ids": [c.id for c in result.chunks],
            }

            if job_id:
                await complete_job(job_id, output)

            return output

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        if job_id:
            _run_async(fail_job(job_id, str(exc), self.request.retries, self.max_retries))
        raise self.retry(exc=exc, countdown=2**self.request.retries * 30)
