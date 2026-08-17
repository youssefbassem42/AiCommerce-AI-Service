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
        assert "organization_id" in call_doc, f"ProductWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"

    async def test_order_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = OrderWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext2",
            data={"currency": "USD"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, f"OrderWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"
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
        assert "organization_id" in call_doc, f"CategoryWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"

    async def test_inventory_writer_uses_organization_id(self, mock_collection, mock_collections):
        writer = InventoryWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext5",
            data={"variant_id": "v1"},
        )
        call_doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert "organization_id" in call_doc, f"InventoryWriter doc should use 'org_id'. Keys: {list(call_doc.keys())}"

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


class TestSyncFieldNormalization:
    """Regression: recommendation cards were missing image/price/url and products
    were never linked to categories because sync wrote a flat image_url (dropped on
    read), ignored variants[] prices and camelCase categoryName."""

    def _product_doc(self, mock_collection):
        return mock_collection.update_one.call_args[0][1]["$set"]

    async def test_product_writer_normalizes_images_and_price_from_variants(self, mock_collection, mock_collections):
        writer = ProductWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext9",
            data={
                "title": "Gaming Laptop RTX",
                "price": None,
                "variants": [{"title": "Black", "price": {"amount": 999.99, "currency": "USD"}}],
                "imageUrl": "https://cdn.example.com/laptop.jpg",
                "productType": "Laptops",
            },
        )
        doc = self._product_doc(mock_collection)
        assert doc["price"] == {"amount": 999.99, "currency": "USD"}
        assert doc["images"] == [
            {"url": "https://cdn.example.com/laptop.jpg", "alt_text": "Gaming Laptop RTX", "position": 1}
        ]
        assert doc["image_url"] == "https://cdn.example.com/laptop.jpg"
        assert doc["handle"] == "gaming-laptop-rtx"
        assert doc["product_type"] == "Laptops"

    async def test_product_writer_normalizes_images_array_shapes(self, mock_collection, mock_collections):
        writer = ProductWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext10",
            data={
                "title": "Sunglasses Retro",
                "images": [
                    {"src": "https://cdn.example.com/a.jpg", "alt": "Front view"},
                    "https://cdn.example.com/b.jpg",
                ],
            },
        )
        doc = self._product_doc(mock_collection)
        assert doc["images"][0]["url"] == "https://cdn.example.com/a.jpg"
        assert doc["images"][0]["alt_text"] == "Front view"
        assert doc["images"][1]["url"] == "https://cdn.example.com/b.jpg"
        assert doc["image_url"] == "https://cdn.example.com/a.jpg"

    async def test_product_writer_resolves_category_from_camel_case_name(self, mock_collection, mock_collections):
        mock_collection.find_one.return_value = {"external_id": "cat-9", "_id": "mongo-id-9"}
        writer = ProductWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="ext11",
            data={"title": "Teapot", "categoryName": "Home"},
        )
        doc = self._product_doc(mock_collection)
        assert doc["category_id"] == "cat-9"
        assert mock_collection.find_one.call_args.args[0] == {"store_id": "s1", "name": "Home"}

    async def test_category_writer_accepts_title_and_camel_case(self, mock_collection, mock_collections):
        writer = CategoryWriter()
        await writer.upsert(
            store_id="s1",
            organization_id="o1",
            external_id="cat-1",
            data={"title": "Electronics", "parentId": "cat-0", "imageUrl": "https://cdn.example.com/cat.jpg"},
        )
        doc = mock_collection.update_one.call_args[0][1]["$set"]
        assert doc["name"] == "Electronics"
        assert doc["parent_id"] == "cat-0"
        assert doc["image_url"] == "https://cdn.example.com/cat.jpg"
        assert doc["handle"] == "electronics"

    async def test_collection_entity_routes_to_category_writer(self, mock_collection, mock_collections):
        from app.application.integration.sync.writers import DynamicEntityWriter

        writer = get_writer("collection")
        assert not isinstance(writer, DynamicEntityWriter)
        assert writer.collection_name() == "categories"

    async def test_flat_image_url_read_back_into_entity(self, mock_collection):
        from app.infrastructure.mongodb.documents.product_document import ProductDocument

        doc = ProductDocument.from_mongo_dict(
            {
                "store_id": "s1",
                "organization_id": "o1",
                "external_id": "23",
                "title": "Sunglasses Retro",
                "status": "active",
                "image_url": "https://cdn.example.com/sunglasses.jpg",
                "price": {"amount": 30.0, "currency": "USD"},
            }
        )
        entity = doc.to_entity()
        assert entity.image_url == "https://cdn.example.com/sunglasses.jpg"
