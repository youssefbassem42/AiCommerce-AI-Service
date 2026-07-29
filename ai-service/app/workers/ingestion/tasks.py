import logging
from typing import Optional

from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.knowledge.extractors import ExtractorFactory
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.tasks.helpers import _run_async, complete_job, fail_job, update_job_progress
from app.application.knowledge.processing.pipeline import ProcessingPipeline
from app.application.knowledge.processing.processor import DocumentProcessor
from app.application.knowledge.chunking.chunking_service import ChunkingService, ChunkingConfig
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument

logger = logging.getLogger(__name__)


@celery_app.task(
    name="knowledge.process_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_document_task(self, document_id: str, file_path: str, mime_type: Optional[str] = None, job_id: Optional[str] = None) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.1, JobStatus.RUNNING)

            repo = KnowledgeRepository()
            extractor_factory = ExtractorFactory()
            pipeline = ProcessingPipeline()
            processor = DocumentProcessor(repo, extractor_factory, pipeline)

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
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)


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
    job_id: Optional[str] = None,
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
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
