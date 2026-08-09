from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.integration.sync.writers import (
    CategoryWriter,
    CustomerWriter,
    DynamicEntityWriter,
    InventoryWriter,
    OrderWriter,
    ProductWriter,
    get_writer,
)


@pytest.fixture
def mock_collection():
    return AsyncMock()


@pytest.fixture
def mock_collections(mock_collection):
    with (
        patch("app.application.integration.sync.writers.get_products_collection", return_value=mock_collection),
        patch("app.application.integration.sync.writers.get_orders_collection", return_value=mock_collection),
        patch("app.application.integration.sync.writers.get_customers_collection", return_value=mock_collection),
        patch("app.application.integration.sync.writers.get_categories_collection", return_value=mock_collection),
        patch("app.application.integration.sync.writers.get_inventory_collection", return_value=mock_collection),
        patch("app.application.integration.sync.writers.get_entities_collection", return_value=mock_collection),
    ):
        yield


class TestWriterBugs:
    async def test_product_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = ProductWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext1",
            data={"title": "Test"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, (
            f"ProductWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"
        )

    async def test_order_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = OrderWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext2",
            data={"currency": "USD"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, (
            f"OrderWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"
        )
        assert "org_id" not in call_doc, f"OrderWriter doc should not use 'org_id'. Got keys: {list(call_doc.keys())}"

    async def test_customer_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = CustomerWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext3",
            data={"email": "test@example.com"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc

    async def test_category_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = CategoryWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext4",
            data={"name": "Test Category"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, (
            f"CategoryWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"
        )

    async def test_inventory_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = InventoryWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext5",
            data={"variant_id": "v1"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, (
            f"InventoryWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"
        )

    async def test_order_writer_preserves_price_types(self, mock_collection, mock_collections):
        writer = OrderWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext3",
            data={"total": 99.99, "subtotal": 50.00, "currency": "USD"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert call_doc["total_price"] == {"amount": 99.99, "currency": "USD"}, (
            f"total_price should be normalized to {{amount, currency}}, got: {call_doc['total_price']}"
        )
        assert call_doc["subtotal_price"] == {"amount": 50.0, "currency": "USD"}, (
            f"subtotal_price should be normalized to {{amount, currency}}, got: {call_doc['subtotal_price']}"
        )

    async def test_dynamic_writer_pops_date_fields_from_data(self, mock_collection, mock_collections):
        with patch("app.application.integration.sync.writers.get_entities_collection", return_value=mock_collection):
            writer = DynamicEntityWriter("test_entity")
            await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext5",
                data={"title": "test", "created_at": "2024-01-01", "price": 100},
            )
            call_doc = mock_collection.update_one.call_args[0][1]["$set"]
            stored_data = call_doc["data"]
            assert "created_at" not in stored_data, "DynamicEntityWriter should pop created_at from data before upsert"
            assert stored_data["title"] == "test"
            assert stored_data["price"] == 100

    async def test_get_writer_returns_dynamic_for_unknown(self):
        writer = get_writer("unknown_entity")
        assert isinstance(writer, DynamicEntityWriter)
        assert writer.collection_name() == "entities"

    async def test_writer_map_has_all_expected_types(self):
        from app.application.integration.sync.writers import WRITER_MAP

        assert "product" in WRITER_MAP
        assert "order" in WRITER_MAP
        assert "customer" in WRITER_MAP
        assert "category" in WRITER_MAP
        assert "inventory" in WRITER_MAP


class TestSyncOrchestratorBugs:
    async def test_total_fetched_counts_records_not_pages(self):
        mock_iter = AsyncMock()
        mock_iter.__aiter__.return_value = [
            MagicMock(data=[{"id": 1}, {"id": 2}, {"id": 3}]),
        ]

        with patch("app.application.integration.sync.orchestrator.PaginationIterator", return_value=mock_iter):
            from app.application.integration.sync.orchestrator import SyncOrchestrator

            orch = SyncOrchestrator()
            entity_result = MagicMock()
            entity_result.total_fetched = 0
            entity_result.total_mapped = 0
            entity_result.errors = []

            connection = MagicMock()
            connection.store_id = "s1"
            connection.organization_id = "o1"

            entity_mapping = MagicMock()
            entity_mapping.entity_type = "product"
            entity_mapping.list_path = "/products"
            entity_mapping.pagination = None
            entity_mapping.list_method = "GET"
            entity_mapping.id_field = "id"

            import app.application.integration.sync.orchestrator as orch_module

            async def dummy_process(self, page, connection, entity_mapping, entity_result, writer, mapped_records):
                pass

            with patch.object(orch_module.SyncOrchestrator, "_process_page", dummy_process):
                client = MagicMock()
                client._client = AsyncMock()
                await orch._sync_entity_type(client, connection, entity_mapping, entity_result)

            assert entity_result.total_fetched == 3, (
                f"total_fetched should be 3 (records in page), got {entity_result.total_fetched}"
            )

    async def test_sync_skips_empty_pages(self):
        mock_iter = AsyncMock()
        mock_iter.__aiter__.return_value = [
            MagicMock(data=[]),
        ]

        with patch("app.application.integration.sync.orchestrator.PaginationIterator", return_value=mock_iter):
            from app.application.integration.sync.orchestrator import SyncOrchestrator

            orch = SyncOrchestrator()
            entity_result = MagicMock()
            entity_result.total_fetched = 0
            entity_result.total_mapped = 0
            entity_result.errors = []

            connection = MagicMock()
            connection.store_id = "s1"
            connection.organization_id = "o1"

            entity_mapping = MagicMock()
            entity_mapping.entity_type = "product"
            entity_mapping.list_path = "/products"
            entity_mapping.pagination = None
            entity_mapping.list_method = "GET"
            entity_mapping.id_field = "id"

            import app.application.integration.sync.orchestrator as orch_module

            async def dummy_process(self, page, connection, entity_mapping, entity_result, writer, mapped_records):
                pass

            with patch.object(orch_module.SyncOrchestrator, "_process_page", dummy_process):
                client = MagicMock()
                client._client = AsyncMock()
                await orch._sync_entity_type(client, connection, entity_mapping, entity_result)

            assert entity_result.total_fetched == 0, (
                f"total_fetched should be 0 for empty page, got {entity_result.total_fetched}"
            )
