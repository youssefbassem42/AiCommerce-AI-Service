import logging

from app.domain.commerce.events.product_events import ProductSynced, ProductDeleted
from app.domain.knowledge.repositories.knowledge_repository import KnowledgeRepository
from app.domain.knowledge.repositories.chunk_repository import ChunkRepository
from app.shared.events.event_handler import IEventHandler

logger = logging.getLogger(__name__)


class ProductSyncHandler(IEventHandler[ProductSynced]):
    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        chunk_repository: ChunkRepository,
    ):
        self._knowledge_repository = knowledge_repository
        self._chunk_repository = chunk_repository

    async def handle(self, event: ProductSynced) -> None:
        logger.info(
            "Product synced, invalidating knowledge for product=%s store=%s platform=%s",
            event.product_id,
            event.store_id,
            event.platform,
        )
        docs = await self._knowledge_repository.find_many(
            {"store_id": event.store_id, "status": "active"}
        )
        for doc in docs:
            doc.status = "pending_reprocess"
            await self._knowledge_repository.update(doc)


class ProductDeletedHandler(IEventHandler[ProductDeleted]):
    def __init__(
        self,
        chunk_repository: ChunkRepository,
    ):
        self._chunk_repository = chunk_repository

    async def handle(self, event: ProductDeleted) -> None:
        logger.info(
            "Product deleted, removing knowledge chunks for product=%s store=%s",
            event.product_id,
            event.store_id,
        )
        chunks = await self._chunk_repository.find_many(
            {"store_id": event.store_id, "product_id": event.product_id}
        )
        for chunk in chunks:
            await self._chunk_repository.delete(chunk.id)
