from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.integration.sync.formatters import (
    format_customer,
    format_order,
    format_product,
    format_record,
    get_formatter,
)
from app.application.integration.sync.knowledge_bridge import CommerceKnowledgeBridge, EntityVectorSyncResult


class TestFormatters:
    def test_format_product_full(self):
        data = {
            "title": "Test Product",
            "status": "active",
            "sku": "SKU001",
            "price": 19.99,
            "description": "A test product",
            "vendor": "TestVendor",
            "product_type": "Physical",
            "tags": ["tag1", "tag2"],
            "weight": 1.5,
            "inventory_quantity": 100,
            "image_url": "https://example.com/img.jpg",
            "category_id": "cat1",
            "handle": "test-product",
        }
        result = format_product(data)
        assert "Test Product" in result
        assert "SKU001" in result
        assert "19.99" in result
        assert "A test product" in result
        assert "TestVendor" in result
        assert "Physical" in result
        assert "tag1" in result or "tag2" in result
        assert "1.5" in result
        assert "100" in result
        assert "img.jpg" in result
        assert "cat1" in result
        assert "test-product" in result

    def test_format_product_minimal(self):
        data = {"title": "Minimal Product"}
        result = format_product(data)
        assert "Minimal Product" in result
        assert "SKU" not in result
        assert "Price" not in result

    def test_format_product_empty(self):
        data = {}
        result = format_product(data)
        assert "(no title)" in result

    def test_format_order_full(self):
        data = {
            "external_id": "ORD-001",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "email": "customer@test.com",
            "customer_id": "c123",
            "subtotal": 100.0,
            "total": 120.0,
            "currency": "USD",
            "shipping_price": 10.0,
            "tax": 10.0,
            "discount": 5.0,
            "notes": "Handle with care",
            "tags": ["urgent"],
        }
        result = format_order(data)
        assert "ORD-001" in result
        assert "paid" in result
        assert "fulfilled" in result
        assert "customer@test.com" in result
        assert "c123" in result
        assert "100.0" in result
        assert "120.0" in result
        assert "USD" in result
        assert "10.0" in result
        assert "Handle with care" in result
        assert "urgent" in result

    def test_format_order_minimal(self):
        data = {"external_id": "ORD-002"}
        result = format_order(data)
        assert "ORD-002" in result
        assert "Status" not in result

    def test_format_customer_full(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@test.com",
            "phone": "+1234567890",
            "tags": ["vip"],
            "accepts_marketing": True,
            "notes": "Prefers email",
        }
        result = format_customer(data)
        assert "John Doe" in result
        assert "john@test.com" in result
        assert "+1234567890" in result
        assert "vip" in result
        assert "True" in result or "true" in result
        assert "Prefers email" in result

    def test_format_customer_minimal(self):
        data = {"email": "anon@test.com"}
        result = format_customer(data)
        assert "anon@test.com" in result
        assert "(no name)" in result

    def test_format_customer_empty(self):
        data = {}
        result = format_customer(data)
        assert "(no name)" in result

    def test_format_record_product(self):
        data = {"title": "Test", "price": 10}
        result = format_record("product", data)
        assert result is not None
        assert "Test" in result

    def test_format_record_unsupported(self):
        data = {"name": "Test"}
        result = format_record("inventory", data)
        assert result is not None
        assert "Test" in result

    def test_get_formatter(self):
        assert get_formatter("product") is not None
        assert get_formatter("order") is not None
        assert get_formatter("customer") is not None
        assert get_formatter("unknown") is not None


class TestCommerceKnowledgeBridge:
    @pytest.fixture
    def mock_vector_store(self):
        vs = AsyncMock()
        vs.collection_exists = AsyncMock(return_value=True)
        vs.delete_by_filter = AsyncMock()
        vs.upsert = AsyncMock()
        return vs

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.embeddings = AsyncMock(
            return_value=MagicMock(
                embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
                model="gemini-embedding-001",
                provider="mock",
                usage=MagicMock(),
            )
        )
        return llm

    @pytest.fixture
    def bridge(self, mock_vector_store, mock_llm):
        return CommerceKnowledgeBridge(
            vector_store=mock_vector_store,
            llm_provider=mock_llm,
        )

    @pytest.mark.asyncio
    async def test_sync_entity_success(self, bridge, mock_vector_store, mock_llm):
        records = [
            {"title": "Product A", "price": 10, "external_id": "p1"},
            {"title": "Product B", "price": 20, "external_id": "p2"},
        ]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=records,
        )
        assert result.total_records == 2
        assert result.total_embedded == 2
        assert result.total_synced == 2
        assert len(result.errors) == 0
        mock_vector_store.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_entity_empty_records(self, bridge, mock_vector_store):
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[],
        )
        assert result.total_records == 0
        assert result.total_synced == 0
        mock_vector_store.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_entity_unsupported_type(self, bridge):
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="inventory",
            records=[{"name": "Test"}],
        )
        assert result.total_records == 1
        assert result.total_synced == 1

    @pytest.mark.asyncio
    async def test_sync_entity_embedding_failure(self, bridge, mock_llm):
        mock_llm.embeddings = AsyncMock(side_effect=RuntimeError("API down"))
        records = [{"title": "Product A", "external_id": "p1"}]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=records,
        )
        assert result.total_embedded == 0
        assert result.total_synced == 0
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_sync_entity_vector_store_upsert_failure(self, bridge, mock_vector_store):
        mock_vector_store.upsert = AsyncMock(side_effect=RuntimeError("Qdrant down"))
        records = [{"title": "Product A", "external_id": "p1"}]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=records,
        )
        assert result.total_synced == 0
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_sync_entity_deletes_stale(self, bridge, mock_vector_store):
        mock_vector_store.collection_exists = AsyncMock(return_value=True)
        records = [{"title": "New Product", "external_id": "p1"}]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=records,
        )
        mock_vector_store.delete_by_filter.assert_called_once()
        assert result.total_synced == 1

    @pytest.mark.asyncio
    async def test_sync_entity_order(self, bridge, mock_vector_store, mock_llm):
        records = [
            {"external_id": "ORD-1", "total": 100, "email": "a@b.com"},
            {"external_id": "ORD-2", "total": 200, "email": "c@d.com"},
        ]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="order",
            records=records,
        )
        assert result.total_records == 2
        assert result.total_synced == 2

    @pytest.mark.asyncio
    async def test_sync_entity_customer(self, bridge, mock_vector_store, mock_llm):
        records = [
            {"first_name": "John", "last_name": "Doe", "email": "john@test.com", "external_id": "c1"},
        ]
        result = await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="customer",
            records=records,
        )
        assert result.total_records == 1
        assert result.total_synced == 1

    def test_entity_vector_sync_result_to_dict(self):
        evsr = EntityVectorSyncResult("product")
        evsr.total_records = 10
        evsr.total_embedded = 8
        evsr.total_synced = 8
        evsr.errors.append("partial failure")
        d = evsr.to_dict()
        assert d["entity_type"] == "product"
        assert d["total_records"] == 10
        assert d["total_embedded"] == 8
        assert d["total_synced"] == 8
        assert len(d["errors"]) == 1


class TestBridgePayloadAndRecordOps:
    @pytest.fixture
    def mock_vector_store(self):
        vs = AsyncMock()
        vs.collection_exists = AsyncMock(return_value=True)
        vs.delete_by_filter = AsyncMock()
        vs.upsert = AsyncMock()
        return vs

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.embeddings = AsyncMock(return_value=MagicMock(embeddings=[[0.1, 0.2, 0.3]], model="gemini-embedding-001"))
        return llm

    @pytest.mark.asyncio
    async def test_product_payload_has_recommendation_fields(self, mock_vector_store, mock_llm):
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"_id": "mongo-id-1", "title": "Retro Sunglasses", "price": 15, "external_id": "23"}],
        )
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert point.id == "s1:product:mongo-id-1:0"
        assert point.payload["product_id"] == "mongo-id-1"
        assert point.payload["product_title"] == "Retro Sunglasses"
        assert point.payload["entity_id"] == "mongo-id-1"
        assert point.payload["document_id"] == "mongo-id-1"
        assert point.payload["store_id"] == "s1"
        assert point.payload["knowledge_version"] == 1

    @pytest.mark.asyncio
    async def test_product_payload_has_canonical_entity_fields(self, mock_vector_store, mock_llm):
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[
                {
                    "_id": "mongo-id-2",
                    "title": "Laptop X",
                    "price": 499.0,
                    "currency": "USD",
                    "category_id": "cat-1",
                    "brand_id": "brand-1",
                    "external_id": "24",
                }
            ],
        )
        point = mock_vector_store.upsert.await_args.args[1][0]
        payload = point.payload
        assert payload["entity_type"] == "product"
        assert payload["entity_id"] == "mongo-id-2"
        assert payload["store_id"] == "s1"
        assert payload["organization_id"] == "o1"
        assert payload["source_type"] == "integration_sync"
        assert payload["document_status"] == "active"
        assert payload["product_id"] == "mongo-id-2"
        assert payload["product_title"] == "Laptop X"
        assert payload["price"] == 499.0
        assert payload["currency"] == "USD"
        assert payload["category_id"] == "cat-1"
        assert payload["brand_id"] == "brand-1"

    @pytest.mark.asyncio
    async def test_non_product_entity_no_product_fields(self, mock_vector_store, mock_llm):
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="category",
            records=[{"external_id": "c1", "name": "Electronics"}],
        )
        point = mock_vector_store.upsert.await_args.args[1][0]
        assert "product_id" not in point.payload
        assert point.payload["document_title"] == "Electronics"

    @pytest.mark.asyncio
    async def test_create_collection_uses_embedding_dimensions(self, mock_vector_store, mock_llm):
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        await bridge.sync_entity(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            records=[{"external_id": "p1", "title": "A"}],
        )
        assert mock_vector_store.create_collection.await_args.kwargs["vector_size"] == 768

    @pytest.mark.asyncio
    async def test_sync_record_single(self, mock_vector_store, mock_llm):
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        result = await bridge.sync_record(
            store_id="s1",
            organization_id="o1",
            entity_type="product",
            record={"_id": "m1", "title": "A", "external_id": "p1"},
        )
        assert result.total_records == 1
        assert result.total_synced == 1

    @pytest.mark.asyncio
    async def test_delete_record_filters_by_entity_key(self, mock_vector_store, mock_llm):
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        await bridge.delete_record(store_id="s1", entity_type="product", entity_key="m1")
        must = mock_vector_store.delete_by_filter.await_args.kwargs["must"]
        assert {"key": "entity_type", "value": "product"} in must
        assert {"key": "document_id", "value": "m1"} in must

    @pytest.mark.asyncio
    async def test_delete_record_missing_collection(self, mock_vector_store, mock_llm):
        mock_vector_store.collection_exists = AsyncMock(return_value=False)
        bridge = CommerceKnowledgeBridge(vector_store=mock_vector_store, llm_provider=mock_llm)
        deleted = await bridge.delete_record(store_id="s1", entity_type="product", entity_key="m1")
        assert deleted == 0
        mock_vector_store.delete_by_filter.assert_not_awaited()
