import asyncio
import logging
from typing import Any, Optional

from app.application.dto.ai_dto import EmbeddingRequest
from app.application.integration.sync.formatters import format_record
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory
from app.infrastructure.qdrant.provider import QdrantProvider
from app.infrastructure.vectorstore.base import VectorRecord

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
BATCH_SIZE = 50
SUPPORTED_ENTITY_TYPES: set[str] | None = None  # None means all types are accepted


class EntityVectorSyncResult:
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
        self.total_records = 0
        self.total_embedded = 0
        self.total_synced = 0
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "total_records": self.total_records,
            "total_embedded": self.total_embedded,
            "total_synced": self.total_synced,
            "errors": self.errors,
        }


class CommerceKnowledgeBridge:
    def __init__(
        self,
        vector_store: Optional[QdrantProvider] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._embedding_model = embedding_model

    async def _ensure_providers(self) -> None:
        if not self._vector_store:
            self._vector_store = QdrantProvider()
            try:
                await asyncio.wait_for(
                    self._vector_store.connect(),
                    timeout=10,
                )
            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                logger.warning("Qdrant unavailable, vector sync will be skipped: %s", e)
                self._vector_store = None
                raise ConnectionError(f"Qdrant not available: {e}")
        if not self._llm_provider:
            factory = LLMProviderFactory()
            self._llm_provider = factory.get_provider("openai")

    async def sync_entity(
        self,
        store_id: str,
        organization_id: str,
        entity_type: str,
        records: list[dict[str, Any]],
    ) -> EntityVectorSyncResult:
        result = EntityVectorSyncResult(entity_type=entity_type)

        if SUPPORTED_ENTITY_TYPES is not None and entity_type not in SUPPORTED_ENTITY_TYPES:
            result.errors.append(f"Entity type '{entity_type}' not supported for vector sync.")
            return result

        if not records:
            logger.info("No records to sync for entity '%s' (store=%s)", entity_type, store_id)
            return result

        result.total_records = len(records)

        try:
            await self._ensure_providers()
        except Exception as e:
            msg = f"Vector store unavailable, skipping sync: {e}"
            logger.warning("%s", msg)
            result.errors.append(msg)
            return result

        collection = f"kb_{store_id}"

        try:
            await self._delete_stale_vectors(collection, store_id, entity_type)
        except Exception as e:
            logger.warning("Failed to delete stale vectors for %s/%s: %s", store_id, entity_type, e)

        formatted = []
        for rec in records:
            text = format_record(entity_type, rec)
            if text:
                formatted.append(text)

        if not formatted:
            logger.warning("No formatted records for entity '%s' (store=%s)", entity_type, store_id)
            return result

        all_points: list[VectorRecord] = []
        for i in range(0, len(formatted), BATCH_SIZE):
            batch = formatted[i : i + BATCH_SIZE]
            batch_records = records[i : i + BATCH_SIZE]
            try:
                request = EmbeddingRequest(input=batch, model=self._embedding_model)
                response = await self._llm_provider.embeddings(request)
                for j, emb in enumerate(response.embeddings):
                    rec_idx = i + j
                    ext_id = str(batch_records[rec_idx].get("external_id", ""))
                    all_points.append(
                        VectorRecord(
                            id=f"{store_id}:{entity_type}:{ext_id}:{rec_idx}",
                            vector=emb,
                            payload={
                                "organization_id": organization_id,
                                "store_id": store_id,
                                "entity_type": entity_type,
                                "external_id": ext_id,
                                "source_type": "integration_sync",
                                "document_id": ext_id,
                                "document_title": f"{entity_type}:{ext_id}",
                                "document_status": "active",
                                "chunk_index": rec_idx,
                                "content": batch[j],
                            },
                        )
                    )
                result.total_embedded += len(response.embeddings)
            except Exception as e:
                logger.exception("Embedding failed for batch %d of '%s'", i // BATCH_SIZE, entity_type)
                result.errors.append(f"Embedding batch failed: {e}")

        if all_points:
            try:
                await self._vector_store.upsert(collection, all_points)
                result.total_synced = len(all_points)
                logger.info(
                    "Synced %d vectors for entity '%s' (store=%s)",
                    len(all_points),
                    entity_type,
                    store_id,
                )
            except Exception as e:
                logger.exception("Vector store upsert failed for '%s'", entity_type)
                result.errors.append(f"Vector store upsert failed: {e}")

        return result

    async def _delete_stale_vectors(
        self,
        collection: str,
        store_id: str,
        entity_type: str,
    ) -> None:
        try:
            exists = await self._vector_store.collection_exists(collection)
            if not exists:
                return
            await self._vector_store.delete_by_filter(
                collection,
                must=[
                    {"key": "store_id", "match": {"value": store_id}},
                    {"key": "entity_type", "match": {"value": entity_type}},
                    {"key": "source_type", "match": {"value": "integration_sync"}},
                ],
                must_not=None,
            )
        except Exception as e:
            logger.warning("Could not delete stale vectors: %s", e)
            raise
