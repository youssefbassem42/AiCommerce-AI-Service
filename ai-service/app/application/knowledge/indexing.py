import logging
from collections.abc import Callable
from typing import Any

from app.application.integration.sync.knowledge_bridge import CommerceKnowledgeBridge
from app.application.integration.sync.records import category_to_record, order_to_record, product_to_record
from app.application.jobs.job_dispatcher import JobDispatcher
from app.domain.job.value_objects import JobType
from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository
from app.infrastructure.mongodb.repositories.commerce_category_repository import CommerceCategoryRepository
from app.infrastructure.mongodb.repositories.commerce_order_repository import CommerceOrderRepository
from app.infrastructure.mongodb.repositories.commerce_product_repository import CommerceProductRepository
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository

logger = logging.getLogger(__name__)

PAGE_SIZE = 200
EMBEDDING_MODEL = "gemini-embedding-001"


class StoreIndexer:
    """Global store indexing: real commerce data + knowledge documents -> tenant RAG vectors.

    Shared by the ``kb.backfill_store_vectors`` celery task, the admin reindex
    endpoint and the CLI backfill script, so every entry point runs the same path.
    """

    def __init__(
        self,
        product_repository: CommerceProductRepository | None = None,
        category_repository: CommerceCategoryRepository | None = None,
        order_repository: CommerceOrderRepository | None = None,
        knowledge_repository: KnowledgeRepository | None = None,
        chunk_repository: ChunkRepository | None = None,
        bridge: CommerceKnowledgeBridge | None = None,
        dispatcher: JobDispatcher | None = None,
    ):
        self._product_repo = product_repository or CommerceProductRepository()
        self._category_repo = category_repository or CommerceCategoryRepository()
        self._order_repo = order_repository or CommerceOrderRepository()
        self._knowledge_repo = knowledge_repository or KnowledgeRepository()
        self._chunk_repo = chunk_repository or ChunkRepository()
        self._bridge = bridge or CommerceKnowledgeBridge()
        self._dispatcher = dispatcher or JobDispatcher()

    async def index_store(
        self,
        store_id: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "store_id": store_id,
            "products": None,
            "categories": None,
            "orders": None,
            "documents": {"chunked": [], "synced": [], "skipped": []},
        }
        summary["products"] = await self._index_products(store_id)
        summary["categories"] = await self._index_categories(store_id)
        summary["orders"] = await self._index_orders(store_id)
        if progress_callback:
            progress_callback(0.7)
        await self._index_knowledge_documents(store_id, summary["documents"])
        if progress_callback:
            progress_callback(1.0)
        return summary

    async def _index_products(self, store_id: str) -> dict[str, Any]:
        return await self._sync_entity_type(store_id, "product", self._iter_products)

    async def _index_categories(self, store_id: str) -> dict[str, Any]:
        return await self._sync_entity_type(store_id, "category", self._iter_categories)

    async def _index_orders(self, store_id: str) -> dict[str, Any]:
        return await self._sync_entity_type(store_id, "order", self._iter_orders)

    async def _iter_products(self, store_id: str):
        skip = 0
        while True:
            items = await self._product_repo.find_by_store(store_id, limit=PAGE_SIZE, skip=skip)
            if not items:
                break
            for entity in items:
                yield product_to_record(entity)
            if len(items) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

    async def _iter_categories(self, store_id: str):
        skip = 0
        while True:
            items = await self._category_repo.find_by_store(store_id, limit=PAGE_SIZE, skip=skip)
            if not items:
                break
            for entity in items:
                yield category_to_record(entity)
            if len(items) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

    async def _iter_orders(self, store_id: str):
        skip = 0
        while True:
            items = await self._order_repo.find_by_store(store_id, limit=PAGE_SIZE, skip=skip)
            if not items:
                break
            for entity in items:
                yield order_to_record(entity)
            if len(items) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

    async def _sync_entity_type(
        self,
        store_id: str,
        entity_type: str,
        records_iter,
    ) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        organization_id = ""
        async for record in records_iter(store_id):
            if not organization_id:
                organization_id = record.get("organization_id", "")
            records.append(record)

        if not records:
            logger.info("No '%s' records to index for store %s", entity_type, store_id)
            return {"entity_type": entity_type, "total_records": 0, "total_synced": 0, "errors": []}

        result = await self._bridge.sync_entity(
            store_id=store_id,
            organization_id=organization_id,
            entity_type=entity_type,
            records=records,
        )
        return result.to_dict()

    async def _index_knowledge_documents(self, store_id: str, target: dict[str, list[str]]) -> None:
        documents = await self._knowledge_repo.find_many({"store_id": store_id, "status": "active"}, limit=10_000)
        for doc in documents:
            if not (doc.processed_text or "").strip():
                target["skipped"].append(f"{doc.id}:no_extracted_text")
                continue
            existing = await self._chunk_repo.find_by_document_id(doc.id, limit=1)
            if existing:
                await self._dispatch_vector_sync(doc, store_id)
                target["synced"].append(doc.id)
            else:
                await self._dispatch_chunking(doc, store_id)
                target["chunked"].append(doc.id)

    async def _dispatch_chunking(self, doc, store_id: str) -> None:
        from app.workers.ingestion.tasks import generate_chunks_task

        job = await self._dispatcher.dispatch(
            job_type=JobType.CHUNK_GENERATION,
            payload={"document_id": doc.id, "strategy": doc.chunking_strategy or "recursive"},
            enqueue=lambda job_id: generate_chunks_task.delay(
                document_id=doc.id,
                strategy=doc.chunking_strategy or "recursive",
                job_id=job_id,
            ),
            store_id=store_id,
            organization_id=None,
            triggered_by="system:store_reindex",
        )
        logger.info("Enqueued chunk-generation %s for doc '%s' (store=%s)", job.id, doc.id, store_id)

    async def _dispatch_vector_sync(self, doc, store_id: str) -> None:
        from app.workers.embedding.tasks import sync_vectors_task

        chunks = await self._chunk_repo.find_by_document_id(doc.id, limit=10_000)
        if not chunks:
            return
        chunk_ids = [c.id for c in chunks]
        collection_name = f"kb_{store_id}"
        job = await self._dispatcher.dispatch(
            job_type=JobType.VECTOR_SYNC,
            payload={"document_id": doc.id, "chunk_count": len(chunk_ids), "collection": collection_name},
            enqueue=lambda job_id: sync_vectors_task.delay(
                chunk_ids=chunk_ids,
                collection_name=collection_name,
                model=EMBEDDING_MODEL,
                job_id=job_id,
                store_id=store_id,
                document_id=doc.id,
            ),
            store_id=store_id,
            organization_id=None,
            triggered_by="system:store_reindex",
        )
        logger.info("Enqueued vector-sync %s for doc '%s' (store=%s)", job.id, doc.id, store_id)
