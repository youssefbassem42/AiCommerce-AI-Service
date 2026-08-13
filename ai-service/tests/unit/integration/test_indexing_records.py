from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.integration.sync.records import category_to_record, order_to_record, product_to_record


def _money(amount: float):
    m = MagicMock()
    m.amount = Decimal(str(amount))
    return m


class TestProductRecordMapper:
    def test_flattens_variants(self):
        entity = MagicMock()
        entity.id = "prod-1"
        entity.organization_id = "org-1"
        entity.external_id = "23"
        entity.title = "Sunglasses Retro"
        entity.description = "Cool shades"
        entity.status = "active"
        entity.product_type = "accessories"
        entity.vendor = "Acme"
        entity.tags = ["retro", "summer"]
        entity.category_id = "cat-1"
        entity.handle = "sunglasses-retro"
        entity.images = [MagicMock(url="https://img/1.png")]

        v1 = MagicMock()
        v1.sku = "SKU-A"
        v1.price = _money(15.0)
        v1.compare_at_price = _money(20.0)
        v1.inventory_quantity = 4
        v2 = MagicMock()
        v2.sku = "SKU-B"
        v2.price = _money(18.0)
        v2.compare_at_price = None
        v2.inventory_quantity = 2
        entity.variants = [v1, v2]

        rec = product_to_record(entity)

        assert rec["_id"] == "prod-1"
        assert rec["external_id"] == "23"
        assert rec["title"] == "Sunglasses Retro"
        assert rec["price"] == 15.0
        assert rec["compare_at_price"] == 20.0
        assert rec["inventory_quantity"] == 6
        assert rec["sku"] == "SKU-A"
        assert rec["image_url"] == "https://img/1.png"
        assert rec["organization_id"] == "org-1"

    def test_no_variants(self):
        entity = MagicMock()
        entity.id = "prod-2"
        entity.organization_id = "org-1"
        entity.external_id = None
        entity.title = "Empty"
        entity.description = None
        entity.status = "draft"
        entity.product_type = None
        entity.vendor = None
        entity.tags = []
        entity.category_id = None
        entity.handle = None
        entity.images = []
        entity.variants = []
        rec = product_to_record(entity)
        assert rec["price"] is None
        assert rec["inventory_quantity"] == 0


class TestCategoryAndOrderRecordMappers:
    def test_category_to_record(self):
        entity = MagicMock()
        entity.id = "cat-1"
        entity.organization_id = "org-1"
        entity.external_id = "1"
        entity.name = "Electronics"
        entity.description = "Gadgets"
        entity.handle = "electronics"
        entity.parent_id = None
        entity.image_url = "https://img/c.png"
        entity.sort_order = 0
        entity.product_count = 5
        rec = category_to_record(entity)
        assert rec["name"] == "Electronics"
        assert rec["_id"] == "cat-1"
        assert rec["product_count"] == 5

    def test_order_to_record(self):
        entity = MagicMock()
        entity.id = "ord-1"
        entity.organization_id = "org-1"
        entity.external_id = "ORD-100"
        entity.customer_id = "c1"
        entity.customer_email = "a@b.com"
        entity.subtotal_price = _money(90.0)
        entity.total_price = _money(100.0)
        entity.total_tax = _money(10.0)
        entity.total_discount = _money(5.0)
        entity.shipping_price = _money(5.0)
        entity.financial_status = "paid"
        entity.fulfillment_status = "fulfilled"
        entity.currency = "USD"
        entity.notes = None
        entity.tags = ["vip"]
        rec = order_to_record(entity)
        assert rec["total_price"] == 100.0
        assert rec["subtotal_price"] == 90.0
        assert rec["customer_email"] == "a@b.com"
        assert rec["financial_status"] == "paid"
        assert rec["_id"] == "ord-1"

    def test_order_formatter_reads_mongo_alias_fields(self):
        from app.application.integration.sync.formatters import format_order

        text = format_order(
            {
                "external_id": "ORD-100",
                "total_price": 100.0,
                "subtotal_price": 90.0,
                "customer_email": "a@b.com",
                "total_tax": 10.0,
                "total_discount": 5.0,
            }
        )
        assert "Total: 100.0" in text
        assert "Subtotal: 90.0" in text
        assert "Customer email: a@b.com" in text
        assert "Tax: 10.0" in text
        assert "Discount: 5.0" in text


class TestStoreIndexer:
    def _entity(self, eid: str, etype: str = "product"):
        e = MagicMock()
        e.id = eid
        e.organization_id = "org-1"
        e.external_id = f"ext-{eid}"
        e.title = f"Title {eid}"
        e.description = f"Desc {eid}"
        e.status = "active"
        e.product_type = None
        e.vendor = None
        e.tags = []
        e.category_id = None
        e.handle = None
        e.images = []
        e.variants = []
        e.name = f"Name {eid}"
        e.updated_at = datetime.now(UTC)
        if etype == "product":
            e.price = None
        return e

    @pytest.mark.asyncio
    async def test_index_store_entities_and_documents(self):
        from app.application.knowledge.indexing import StoreIndexer

        product_repo = MagicMock()
        product_repo.find_by_store = AsyncMock(return_value=[self._entity("p1"), self._entity("p2")])
        category_repo = MagicMock()
        category_repo.find_by_store = AsyncMock(return_value=[self._entity("c1", "category")])
        order_repo = MagicMock()
        order_repo.find_by_store = AsyncMock(return_value=[])

        knowledge_repo = MagicMock()
        doc_with_text = MagicMock()
        doc_with_text.id = "doc-1"
        doc_with_text.status = "active"
        doc_with_text.processed_text = "some real text"
        doc_with_text.chunking_strategy = "recursive"
        doc_no_text = MagicMock()
        doc_no_text.id = "doc-2"
        doc_no_text.status = "active"
        doc_no_text.processed_text = ""
        doc_no_text.chunking_strategy = "recursive"
        knowledge_repo.find_many = AsyncMock(return_value=[doc_with_text, doc_no_text])

        chunk_repo = MagicMock()
        chunk_repo.find_by_document_id = AsyncMock(side_effect=[[], [MagicMock(id="chunk-1")]])

        bridge = MagicMock()
        bridge.sync_entity = AsyncMock(return_value=MagicMock(to_dict=lambda: {"synced": 2}))

        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock(return_value=MagicMock(id="job-1"))

        indexer = StoreIndexer(
            product_repository=product_repo,
            category_repository=category_repo,
            order_repository=order_repo,
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
            bridge=bridge,
            dispatcher=dispatcher,
        )

        summary = await indexer.index_store("store-1")

        assert summary["products"]["synced"] == 2
        assert summary["categories"]["synced"] == 2
        assert bridge.sync_entity.await_count == 2
        assert summary["documents"]["chunked"] == ["doc-1"]
        assert summary["documents"]["skipped"] == ["doc-2:no_extracted_text"]
        assert dispatcher.dispatch.await_count == 1

    @pytest.mark.asyncio
    async def test_index_store_doc_with_chunks_dispatches_vector_sync(self):
        from app.application.knowledge.indexing import StoreIndexer

        product_repo = MagicMock()
        product_repo.find_by_store = AsyncMock(return_value=[])
        category_repo = MagicMock()
        category_repo.find_by_store = AsyncMock(return_value=[])
        order_repo = MagicMock()
        order_repo.find_by_store = AsyncMock(return_value=[])

        doc = MagicMock()
        doc.id = "doc-1"
        doc.status = "active"
        doc.processed_text = "real text"
        doc.chunking_strategy = "recursive"
        knowledge_repo = MagicMock()
        knowledge_repo.find_many = AsyncMock(return_value=[doc])

        chunk_repo = MagicMock()
        chunk_repo.find_by_document_id = AsyncMock(return_value=[MagicMock(id="chunk-1")])

        bridge = MagicMock()
        dispatcher = MagicMock()
        dispatcher.dispatch = AsyncMock(return_value=MagicMock(id="job-1"))

        indexer = StoreIndexer(
            product_repository=product_repo,
            category_repository=category_repo,
            order_repository=order_repo,
            knowledge_repository=knowledge_repo,
            chunk_repository=chunk_repo,
            bridge=bridge,
            dispatcher=dispatcher,
        )

        summary = await indexer.index_store("store-1")

        assert summary["documents"]["synced"] == ["doc-1"]
        dispatched_type = dispatcher.dispatch.await_args.kwargs["job_type"]
        assert dispatched_type.value == "vector_sync"
