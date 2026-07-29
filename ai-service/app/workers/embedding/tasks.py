import logging
from typing import Any, Optional

from app.core.celery_app import celery_app
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.collections import get_knowledge_chunks_collection
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.tasks.helpers import _run_async, complete_job, fail_job, update_job_progress
from app.application.dto.ai_dto import EmbeddingRequest
from app.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


@celery_app.task(
    name="knowledge.generate_embeddings",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def generate_embeddings_task(
    self,
    chunk_ids: list[str],
    model: str = "gemini-embedding-001",
    job_id: Optional[str] = None,
) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.0, JobStatus.RUNNING)

            chunk_repo = ChunkRepository()
            factory = LLMProviderFactory()
            model_info = ModelRegistry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Embedding model '{model}' not found in registry")
            provider = factory.get_provider(model_info.provider)

            processed = 0
            errors = 0

            for batch_start in range(0, len(chunk_ids), BATCH_SIZE):
                batch_ids = chunk_ids[batch_start:batch_start + BATCH_SIZE]
                chunks = []
                for cid in batch_ids:
                    chunk = await chunk_repo.find_by_id(cid)
                    if chunk:
                        chunks.append(chunk)

                if not chunks:
                    continue

                texts = [c.content for c in chunks]
                request = EmbeddingRequest(input=texts, model=model)
                response = await provider.embeddings(request)

                if len(response.embeddings) != len(chunks):
                    logger.warning(
                        "Embedding count mismatch: got %d, expected %d",
                        len(response.embeddings), len(chunks),
                    )

                for chunk, embedding in zip(chunks, response.embeddings):
                    chunk.embedding_id = chunk.id
                    await chunk_repo.update(chunk)

                processed += len(chunks)
                errors += len(batch_ids) - len(chunks)

                if job_id:
                    progress = min(1.0, (batch_start + len(batch_ids)) / len(chunk_ids))
                    await update_job_progress(job_id, progress)

            if job_id:
                await update_job_progress(job_id, 1.0)

            result = {
                "total_chunks": len(chunk_ids),
                "processed": processed,
                "errors": errors,
                "model": model,
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
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


@celery_app.task(
    name="knowledge.sync_vectors",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def sync_vectors_task(
    self,
    chunk_ids: list[str],
    collection_name: str = "kb_default",
    model: str = "gemini-embedding-001",
    job_id: Optional[str] = None,
) -> dict:
    def _run():
        async def _async_run():
            if job_id:
                await update_job_progress(job_id, 0.0, JobStatus.RUNNING)

            from app.infrastructure.qdrant.provider import QdrantProvider
            from app.infrastructure.vectorstore.base import VectorRecord

            chunk_repo = ChunkRepository()
            factory = LLMProviderFactory()
            model_info = ModelRegistry.get_model_info(model)
            if not model_info:
                raise ValueError(f"Model '{model}' not found in registry")
            provider = factory.get_provider(model_info.provider)

            qdrant = QdrantProvider()
            try:
                await qdrant.connect()
                exists = await qdrant.collection_exists(collection_name)
                if not exists:
                    await qdrant.create_collection(
                        collection_name=collection_name,
                        vector_size=1536,
                        distance="Cosine",
                    )

                processed = 0
                for batch_start in range(0, len(chunk_ids), BATCH_SIZE):
                    batch_ids = chunk_ids[batch_start:batch_start + BATCH_SIZE]
                    chunks = []
                    for cid in batch_ids:
                        chunk = await chunk_repo.find_by_id(cid)
                        if chunk:
                            chunks.append(chunk)

                    if not chunks:
                        continue

                    texts = [c.content for c in chunks]
                    request = EmbeddingRequest(input=texts, model=model)
                    response = await provider.embeddings(request)

                    points = []
                    for chunk, embedding in zip(chunks, response.embeddings):
                        doc = await chunk_repo.find_by_id(chunk.document_id) if hasattr(chunk, 'document_id') else None
                        payload = {
                            "chunk_id": chunk.id,
                            "document_id": chunk.document_id,
                            "content": chunk.content[:2000],
                            "chunk_index": chunk.chunk_index,
                            "language": chunk.metadata.get("language"),
                            "source_type": chunk.metadata.get("source_type"),
                            "store_id": chunk.metadata.get("store_id"),
                            "organization_id": chunk.metadata.get("organization_id"),
                            "document_title": doc.title if doc else chunk.metadata.get("parent_title", ""),
                            "knowledge_scope": chunk.metadata.get("knowledge_scope"),
                            "business_version": chunk.metadata.get("business_version"),
                        }
                        points.append(VectorRecord(id=chunk.id, vector=embedding, payload=payload))

                    if points:
                        inserted = await qdrant.upsert(collection_name, points)
                        processed += inserted

                    if job_id:
                        progress = min(1.0, (batch_start + BATCH_SIZE) / len(chunk_ids))
                        await update_job_progress(job_id, progress)

                result = {
                    "collection": collection_name,
                    "total_chunks": len(chunk_ids),
                    "synced": processed,
                    "model": model,
                }

                if job_id:
                    await complete_job(job_id, result)

                return result

            finally:
                await qdrant.disconnect()

        return _run_async(_async_run())

    try:
        return _run()
    except Exception as exc:
        if job_id:
            _run_async(fail_job(job_id, str(exc), self.request.retries, self.max_retries))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
