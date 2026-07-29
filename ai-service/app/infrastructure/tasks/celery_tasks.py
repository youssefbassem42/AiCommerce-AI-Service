import asyncio
import time
import logging
from typing import List, Dict, Any
from app.core.celery_app import celery_app
from app.infrastructure.providers.factory import LLMProviderFactory
from app.application.dto.ai_dto import EmbeddingRequest, ChatRequest, MessageDTO
from app.infrastructure.repositories.conversation_repository import ConversationRepository
from app.core.model_registry import ModelRegistry
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.infrastructure.knowledge.extractors import ExtractorFactory
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository
from app.infrastructure.mongodb.collections import get_knowledge_versions_collection
from app.infrastructure.mongodb.documents.knowledge_version_document import (
    KnowledgeVersionDocument,
)

logger = logging.getLogger("ai_service")

def _run_async(coro):
    """Helper to run async coroutines synchronously in Celery worker processes."""
    return asyncio.run(coro)

@celery_app.task(name="ai.generate_embeddings")
def generate_embeddings_task(texts: List[str], model: str) -> List[List[float]]:
    """
    Generate embeddings for a list of texts in the background.
    """
    async def _async_run():
        model_info = ModelRegistry.get_model_info(model)
        if not model_info:
            raise ValueError(f"Model '{model}' not found in registry.")
            
        factory = LLMProviderFactory()
        provider = factory.get_provider(model_info.provider)
        
        request = EmbeddingRequest(input=texts, model=model)
        response = await provider.embeddings(request)
        return response.embeddings

    logger.info(f"Triggering background embedding generation for {len(texts)} items using {model}")
    return _run_async(_async_run())

@celery_app.task(name="ai.summarize_conversation")
def summarize_conversation_task(conversation_id: str, model: str = "gpt-4o-mini") -> str:
    """
    Generate a summary of a conversation and update its metadata in MongoDB.
    """
    async def _async_run():
        repo = ConversationRepository()
        conversation = await repo.get_conversation(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation '{conversation_id}' not found.")
            
        messages = conversation.get("messages", [])
        if not messages:
            return "No messages to summarize."

        # Compile message text
        text_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                content_str = " ".join([str(c) for c in content])
            else:
                content_str = str(content)
            text_parts.append(f"{role.capitalize()}: {content_str}")
        
        full_transcript = "\n".join(text_parts)
        
        # Call Chat Service / Provider to summarize
        model_info = ModelRegistry.get_model_info(model)
        if not model_info:
            raise ValueError(f"Model '{model}' not found in registry.")
            
        factory = LLMProviderFactory()
        provider = factory.get_provider(model_info.provider)
        
        prompt = f"Please provide a concise summary of the following conversation transcript:\n\n{full_transcript}"
        request = ChatRequest(
            messages=[MessageDTO(role="user", content=prompt)],
            model=model
        )
        response = await provider.chat(request)
        summary = response.message.content
        
        # Save summary to conversation metadata
        metadata = conversation.get("metadata", {})
        metadata["summary"] = summary
        metadata["summarized_at"] = time.time()
        
        await repo.collection.update_one(
            {"conversation_id": conversation_id},
            {"$set": {"metadata": metadata}}
        )
        return summary

    logger.info(f"Triggering background summarization for conversation: {conversation_id}")
    return _run_async(_async_run())


# ---------------------------------------------------------------------------
# Knowledge Sync Tasks  (orchestrated by KnowledgeSyncCoordinator)
# ---------------------------------------------------------------------------


@celery_app.task(name="kb.extract_document", bind=True, max_retries=3, default_retry_delay=30)
def extract_document_task(self, doc_id: str, file_path: str, org_id: str, store_id: str) -> bool:
    """Extract text from a document file in the background."""
    async def _run() -> bool:
        tenant = TenantContext(organization_id=org_id, store_id=store_id)
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
def chunk_document_task(self, doc_id: str, config_dict: dict, org_id: str, store_id: str) -> int:
    """Chunk a processed document in the background."""
    async def _run() -> int:
        repo = KnowledgeRepository()
        doc = await repo.find_by_id(doc_id)
        if not doc:
            logger.warning("chunk_document_task: document '%s' not found", doc_id)
            return 0
        from app.application.knowledge.chunking.config import ChunkingConfig
        from app.application.knowledge.chunking.chunking_service import ChunkingService
        from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository

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


@celery_app.task(name="kb.embed_chunks", bind=True, max_retries=3, default_retry_delay=30)
def embed_chunks_task(self, doc_id: str, org_id: str, store_id: str) -> int:
    """Generate embeddings for all chunks of a document."""
    async def _run() -> int:
        from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
        from app.infrastructure.providers.factory import LLMProviderFactory
        from app.application.dto.ai_dto import EmbeddingRequest

        chunk_repo = ChunkRepository()
        chunks = await chunk_repo.find_by_document_id(doc_id, limit=10_000)
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        factory = LLMProviderFactory()
        provider = factory.get_provider("openai")
        request = EmbeddingRequest(input=texts, model="gemini-embedding-001")
        response = await provider.embeddings(request)

        from app.infrastructure.vectorstore.base import VectorRecord
        from app.infrastructure.qdrant.provider import QdrantProvider

        vs = QdrantProvider()
        await vs.connect()
        collection = f"kb_{store_id}"
        points = [VectorRecord(id=c.id, vector=emb, payload={"chunk_id": c.id, "document_id": c.document_id}) for c, emb in zip(chunks, response.embeddings)]
        await vs.upsert(collection, points)
        await vs.disconnect()

        logger.info("Embedded %d chunks for doc '%s'", len(chunks), doc_id)
        return len(chunks)

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("embed_chunks_task failed for doc '%s': %s", doc_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="kb.sync_vector_db", bind=True, max_retries=2, default_retry_delay=60)
def sync_vector_db_task(self, store_id: str, org_id: str, store_slug: str) -> bool:
    """Sync pending chunk embeddings to the vector database for a store."""
    async def _run() -> bool:
        from app.infrastructure.qdrant.provider import QdrantProvider

        vs = QdrantProvider()
        await vs.connect()
        collection = f"kb_{store_slug or store_id}"
        exists = await vs.collection_exists(collection)
        if not exists:
            await vs.create_collection(collection, vector_size=1536)
        await vs.disconnect()
        logger.info("Vector DB sync complete for store '%s'", store_id)
        return True

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("sync_vector_db_task failed for store '%s': %s", store_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="kb.generate_summary", bind=True, max_retries=2, default_retry_delay=60)
def generate_summary_task(self, store_id: str, model: str, org_id: str, store_slug: str) -> bool:
    """Regenerate the business summary for a store."""
    async def _run() -> bool:
        from app.infrastructure.providers.factory import LLMProviderFactory
        from app.application.knowledge.generation.service import BusinessSummaryGenerationService
        from app.application.knowledge.generation.config import GenerationConfig
        from app.infrastructure.mongodb.repositories.business_summary_repository import (
            BusinessSummaryRepository,
        )

        repo = KnowledgeRepository()
        summary_repo = BusinessSummaryRepository()
        factory = LLMProviderFactory()
        provider = factory.get_provider("openai")
        gen_service = BusinessSummaryGenerationService(
            knowledge_repository=repo,
            summary_repository=summary_repo,
            provider=provider,
        )
        config = GenerationConfig(model=model)
        await gen_service.generate(store_id, config)
        logger.info("Summary regenerated for store '%s'", store_id)
        return True

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error("generate_summary_task failed for store '%s': %s", store_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(name="kb.bump_version", bind=True)
def bump_version_task(self, store_id: str, version: int, org_id: str, store_slug: str) -> bool:
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


def _build_processor(repo: KnowledgeRepository) -> "DocumentProcessor":
    from app.application.knowledge.processing.processor import DocumentProcessor
    from app.application.knowledge.processing.pipeline import ProcessingPipeline

    return DocumentProcessor(
        repository=repo,
        extractor_factory=ExtractorFactory(),
        pipeline=ProcessingPipeline(),
    )
