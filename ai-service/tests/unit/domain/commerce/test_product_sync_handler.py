import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

from app.application.knowledge.event_handlers.product_sync_handler import (
    ProductSyncHandler,
    ProductDeletedHandler,
)
from app.domain.commerce.events.product_events import ProductSynced, ProductDeleted
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk


@pytest.mark.asyncio
class TestProductSyncHandler:
    async def test_product_synced_invalidates_knowledge_documents(self):
        knowledge_repo = AsyncMock()
        chunk_repo = AsyncMock()

        existing_doc = MagicMock(spec=KnowledgeDocument)
        existing_doc.status = "active"
        existing_doc.store_id = "store-1"
        existing_doc.id = "doc-1"

        knowledge_repo.find_many.return_value = [existing_doc]

        handler = ProductSyncHandler(
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
        )

        event = ProductSynced(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            platform="shopify",
            sync_session_id="sync-1",
        )

        await handler.handle(event)

        assert existing_doc.status == "pending_reprocess"
        knowledge_repo.update.assert_called_once_with(existing_doc)

    async def test_product_synced_no_documents_to_invalidate(self):
        knowledge_repo = AsyncMock()
        chunk_repo = AsyncMock()
        knowledge_repo.find_many.return_value = []

        handler = ProductSyncHandler(
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
        )

        event = ProductSynced(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            platform="shopify",
            sync_session_id="sync-1",
        )

        await handler.handle(event)

        knowledge_repo.update.assert_not_called()

    async def test_product_synced_filter_applied_correctly(self):
        knowledge_repo = AsyncMock()
        chunk_repo = AsyncMock()

        knowledge_repo.find_many.return_value = []

        handler = ProductSyncHandler(
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
        )

        event = ProductSynced(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            platform="shopify",
            sync_session_id="sync-1",
        )

        await handler.handle(event)

        knowledge_repo.find_many.assert_called_once_with(
            {"store_id": "store-1", "status": "active"}
        )


@pytest.mark.asyncio
class TestProductDeletedHandler:
    async def test_product_deleted_removes_chunks(self):
        chunk_repo = AsyncMock()

        chunk1 = MagicMock(spec=KnowledgeChunk)
        chunk1.id = "chunk-1"
        chunk2 = MagicMock(spec=KnowledgeChunk)
        chunk2.id = "chunk-2"

        chunk_repo.find_many.return_value = [chunk1, chunk2]

        handler = ProductDeletedHandler(chunk_repository=chunk_repo)

        event = ProductDeleted(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
        )

        await handler.handle(event)

        chunk_repo.find_many.assert_called_once_with(
            {"store_id": "store-1", "product_id": "prod-1"}
        )
        chunk_repo.delete.assert_any_call("chunk-1")
        chunk_repo.delete.assert_any_call("chunk-2")
        assert chunk_repo.delete.call_count == 2

    async def test_product_deleted_no_chunks(self):
        chunk_repo = AsyncMock()
        chunk_repo.find_many.return_value = []

        handler = ProductDeletedHandler(chunk_repository=chunk_repo)

        event = ProductDeleted(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
        )

        await handler.handle(event)

        chunk_repo.delete.assert_not_called()
