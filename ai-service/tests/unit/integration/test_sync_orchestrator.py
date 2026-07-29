import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.integration.sync.knowledge_bridge import CommerceKnowledgeBridge
from app.application.integration.sync.orchestrator import SyncOrchestrator, EntitySyncResult, SyncResult
from app.application.integration.sync.writers import (
    ProductWriter,
    OrderWriter,
    CustomerWriter,
    CategoryWriter,
    InventoryWriter,
    get_writer,
)
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.value_objects.auth_config import AuthConfig
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle


@pytest.fixture
def mock_collection():
    coll = AsyncMock()
    coll.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id", modified_count=0))
    return coll


class TestEntityWriters:
    @pytest.mark.asyncio
    async def test_product_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_products_collection", return_value=mock_collection):
            writer = ProductWriter()
            result = await writer.upsert(
                store_id="s1", org_id="o1", external_id="ext1",
                data={"title": "Test Product", "price": 19.99, "sku": "SKU001", "status": "active"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()
            call_args = mock_collection.update_one.call_args[0]
            assert call_args[0] == {"store_id": "s1", "external_id": "ext1"}

    @pytest.mark.asyncio
    async def test_order_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_orders_collection", return_value=mock_collection):
            writer = OrderWriter()
            result = await writer.upsert(
                store_id="s1", org_id="o1", external_id="ext2",
                data={"email": "test@test.com", "total": 100.0, "currency": "USD"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_customer_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_customers_collection", return_value=mock_collection):
            writer = CustomerWriter()
            result = await writer.upsert(
                store_id="s1", org_id="o1", external_id="ext3",
                data={"email": "cust@test.com", "first_name": "John", "last_name": "Doe"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_category_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_categories_collection", return_value=mock_collection):
            writer = CategoryWriter()
            result = await writer.upsert(
                store_id="s1", org_id="o1", external_id="ext4",
                data={"name": "Electronics", "description": "Gadgets"},
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_inventory_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_inventory_collection", return_value=mock_collection):
            writer = InventoryWriter()
            result = await writer.upsert(
                store_id="s1", org_id="o1", external_id="ext5",
                data={"inventory_quantity": 50, "product_id": "p1", "variant_id": "v1"},
            )
            assert result is True

    def test_get_writer_known_types(self):
        assert get_writer("product") is not None
        assert get_writer("order") is not None
        assert get_writer("customer") is not None
        assert get_writer("category") is not None
        assert get_writer("inventory") is not None

    def test_get_writer_unknown_type(self):
        from app.application.integration.sync.writers import DynamicEntityWriter
        writer = get_writer("unknown")
        assert writer is not None
        assert isinstance(writer, DynamicEntityWriter)


class TestSyncOrchestrator:
    @pytest.fixture
    def connection(self):
        auth = AuthConfig(type="apiKey", name="X-API-Key")
        pagination = PaginationConfig(style=PaginationStyle.NONE)
        field_mappings = [
            FieldMapping(source="name", target="title"),
            FieldMapping(source="price", target="price"),
        ]
        entity_mapping = EntityMapping(
            entity_type="product",
            list_path="/products.json",
            list_method="GET",
            id_field="id",
            pagination=pagination,
            field_mappings=field_mappings,
        )
        return IntegrationConnection(
            id="conn1",
            store_id="s1",
            organization_id="o1",
            name="Test Shopify",
            platform_name="shopify",
            status=ConnectionStatus.ACTIVE,
            auth_config=auth,
            encrypted_credentials="encrypted_key",
            entity_mappings=[entity_mapping],
            discovered_endpoints=[{"server": "https://test.myshopify.com"}],
        )

    @pytest.fixture
    def mock_repo(self, connection):
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=connection)
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def orchestrator(self, mock_repo):
        return SyncOrchestrator(repository=mock_repo)

    @pytest.mark.asyncio
    async def test_sync_not_found(self, orchestrator, mock_repo):
        mock_repo.find_by_id = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await orchestrator.sync_connection("nonexistent")

    @pytest.mark.asyncio
    async def test_sync_inactive_connection(self, orchestrator, mock_repo, connection):
        connection.status = ConnectionStatus.INACTIVE
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"
        assert "not active" in (result.error or "")

    @pytest.mark.asyncio
    async def test_sync_no_mappings(self, orchestrator, connection):
        connection.entity_mappings = []
        mock_repo = AsyncMock()
        mock_repo.find_by_id = AsyncMock(return_value=connection)
        mock_repo.update = AsyncMock()
        orch = SyncOrchestrator(repository=mock_repo)
        result = await orch.sync_connection("conn1")
        assert result.status == "completed"
        assert "No entity mappings" in (result.error or "")

    @pytest.mark.asyncio
    async def test_sync_no_base_url(self, orchestrator, connection):
        connection.discovered_endpoints = []
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_sync_no_writer_for_entity_type(self, orchestrator, connection):
        connection.entity_mappings[0].entity_type = "unknown"
        connection.encrypted_credentials = None
        result = await orchestrator.sync_connection("conn1")
        assert result.entity_results[0].entity_type == "unknown"

    @pytest.mark.asyncio
    async def test_sync_no_list_path(self, orchestrator, connection):
        connection.entity_mappings[0].list_path = None
        connection.encrypted_credentials = None
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "completed"
        errs = result.entity_results[0].errors
        assert any("no list_path" in e.lower() for e in errs)

    def test_entity_sync_result_to_dict(self):
        esr = EntitySyncResult("product")
        esr.total_fetched = 5
        esr.total_mapped = 4
        esr.total_upserted = 3
        d = esr.to_dict()
        assert d["entity_type"] == "product"
        assert d["total_fetched"] == 5
        assert d["total_mapped"] == 4
        assert d["total_upserted"] == 3

    def test_sync_result_to_dict(self):
        sr = SyncResult("conn1", "s1")
        sr.status = "completed"
        sr.completed_at = sr.started_at
        sr.entity_results.append(EntitySyncResult("product"))
        d = sr.to_dict()
        assert d["connection_id"] == "conn1"
        assert d["store_id"] == "s1"
        assert d["status"] == "completed"
        assert len(d["entity_results"]) == 1

    def test_sync_result_duration(self):
        sr = SyncResult("conn1", "s1")
        assert sr.total_duration_seconds is None
        sr.completed_at = sr.started_at
        assert sr.total_duration_seconds == 0.0
