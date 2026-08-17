from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.integration.sync.orchestrator import EntitySyncResult, SyncOrchestrator, SyncResult
from app.application.integration.sync.writers import (
    CategoryWriter,
    CustomerWriter,
    DynamicEntityWriter,
    InventoryWriter,
    OrderWriter,
    ProductWriter,
    get_writer,
)
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.exceptions import IntegrationApiException
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle
from app.infrastructure.http.pagination import PagePayload


@pytest.fixture
def mock_collection():
    coll = AsyncMock()
    coll.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id", modified_count=0))
    return coll


class FakePagination:
    """Async paginator stand-in: yields fixed pages, then raises a fixed exception once."""

    def __init__(self, pages=None, exc=None, fail_after=None):
        self._pages = list(pages or [])
        self._exc = exc
        self._fail_after = fail_after

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._fail_after is not None and self._fail_after <= 0:
            raise StopAsyncIteration
        if self._fail_after is not None:
            self._fail_after -= 1
        if self._pages:
            return self._pages.pop(0)
        if self._exc is not None:
            exc, self._exc = self._exc, None
            raise exc
        raise StopAsyncIteration


class TestGetWriter:
    def test_dedicated_writers_match_case_insensitively(self):
        """REGRESSION: entity types arrive capitalized from the mapping agent
        ('Product'), but WRITER_MAP keys are lowercase — mismatched entities
        silently fell through to DynamicEntityWriter (generic `entities`
        collection) instead of products/customers/categories/orders/inventory."""
        assert isinstance(get_writer("Product"), ProductWriter)
        assert isinstance(get_writer("product"), ProductWriter)
        assert isinstance(get_writer("Customer"), CustomerWriter)
        assert isinstance(get_writer("Category"), CategoryWriter)
        assert isinstance(get_writer("Order"), OrderWriter)
        assert isinstance(get_writer("Inventory"), InventoryWriter)
        assert isinstance(get_writer("Discount"), DynamicEntityWriter)


class TestEntityWriters:
    @pytest.mark.asyncio
    async def test_product_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_products_collection", return_value=mock_collection):
            writer = ProductWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext1",
                data={"title": "Test Product", "price": 19.99, "sku": "SKU001", "status": "active"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()
            call_args = mock_collection.update_one.call_args[0]
            assert call_args[0] == {"store_id": "s1", "external_id": "ext1"}

    @pytest.mark.asyncio
    async def test_product_writer_resolves_category_id_from_name(self, mock_collection):
        products = AsyncMock()
        products.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id", modified_count=0))
        categories = AsyncMock()
        categories.find_one = AsyncMock(side_effect=[{"external_id": "5", "name": "Accessories"}, None])
        with (
            patch("app.application.integration.sync.writers.get_products_collection", return_value=products),
            patch("app.application.integration.sync.writers.get_categories_collection", return_value=categories),
        ):
            writer = ProductWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext1",
                data={"title": "Bag", "price": 55.0, "product_type": "Accessories"},
            )
            assert result is True
            categories.find_one.assert_awaited_once()
            doc = products.update_one.call_args[0][1]["$set"]
            assert doc["category_id"] == "5"

    @pytest.mark.asyncio
    async def test_product_writer_category_lookup_case_insensitive_fallback(self, mock_collection):
        products = AsyncMock()
        products.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id", modified_count=0))
        categories = AsyncMock()
        categories.find_one = AsyncMock(side_effect=[None, {"external_id": "2", "name": "Fashion"}])
        with (
            patch("app.application.integration.sync.writers.get_products_collection", return_value=products),
            patch("app.application.integration.sync.writers.get_categories_collection", return_value=categories),
        ):
            writer = ProductWriter()
            await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext1",
                data={"title": "Dress", "price": 55.0, "product_type": "fashion"},
            )
            assert categories.find_one.await_count == 2
            doc = products.update_one.call_args[0][1]["$set"]
            assert doc["category_id"] == "2"

    @pytest.mark.asyncio
    async def test_product_writer_keeps_explicit_category_id(self, mock_collection):
        products = AsyncMock()
        products.update_one = AsyncMock(return_value=MagicMock(upserted_id="new_id", modified_count=0))
        categories = AsyncMock()
        with (
            patch("app.application.integration.sync.writers.get_products_collection", return_value=products),
            patch("app.application.integration.sync.writers.get_categories_collection", return_value=categories),
        ):
            writer = ProductWriter()
            await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext1",
                data={"title": "Bag", "price": 55.0, "category_id": "7", "product_type": "Accessories"},
            )
            categories.find_one.assert_not_awaited()
            doc = products.update_one.call_args[0][1]["$set"]
            assert doc["category_id"] == "7"

    @pytest.mark.asyncio
    async def test_order_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_orders_collection", return_value=mock_collection):
            writer = OrderWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext2",
                data={"email": "test@test.com", "total": 100.0, "currency": "USD"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_customer_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_customers_collection", return_value=mock_collection):
            writer = CustomerWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext3",
                data={"email": "cust@test.com", "first_name": "John", "last_name": "Doe"},
            )
            assert result is True
            mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_category_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_categories_collection", return_value=mock_collection):
            writer = CategoryWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext4",
                data={"name": "Electronics", "description": "Gadgets"},
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_inventory_writer_upsert(self, mock_collection):
        with patch("app.application.integration.sync.writers.get_inventory_collection", return_value=mock_collection):
            writer = InventoryWriter()
            result = await writer.upsert(
                store_id="s1",
                organization_id="o1",
                external_id="ext5",
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
    async def test_sync_inactive_with_undecryptable_credentials_is_blocked(self, orchestrator, mock_repo, connection):
        connection.status = ConnectionStatus.INACTIVE
        connection.encrypted_credentials = "not-a-valid-blob"
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"
        assert "not active" in (result.error or "")

    @pytest.mark.asyncio
    async def test_sync_error_status_with_credentials_is_self_healing(self, orchestrator, mock_repo, connection):
        from app.infrastructure.http.pagination import PagePayload
        from app.infrastructure.security.key_manager import KeyManager

        connection.status = ConnectionStatus.ERROR
        connection.encrypted_credentials = KeyManager().encrypt_secret('{"token": "real-value"}')
        orchestrator._vector_sync_enabled = False
        llm = AsyncMock()
        llm.fingerprint.return_value = "fp"
        llm.build_entity_mapping = AsyncMock(return_value=None)
        orchestrator._llm_mapper = llm
        writer = AsyncMock(spec=ProductWriter)
        writer.upsert = AsyncMock(return_value=True)
        page = PagePayload(data=[{"id": 1, "name": "Chair", "price": 10.0}], page_number=1, raw_response={})
        with (
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                return_value=FakePagination(pages=[page]),
            ),
        ):
            result = await orchestrator.sync_connection("conn1")
        assert result.status == "completed"
        assert result.error is None
        assert connection.status == ConnectionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_sync_inactive_without_credentials_is_allowed(self, orchestrator, connection):
        connection.status = ConnectionStatus.INACTIVE
        connection.encrypted_credentials = None
        connection.entity_mappings[0].list_path = None
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"
        assert "not active" not in (result.error or "")

    @pytest.mark.asyncio
    async def test_sync_inactive_with_empty_encrypted_credentials_is_allowed(self, orchestrator, connection):
        from app.infrastructure.security.key_manager import KeyManager

        connection.status = ConnectionStatus.INACTIVE
        connection.encrypted_credentials = KeyManager().encrypt_secret("{}")
        connection.entity_mappings[0].list_path = None
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"
        assert "not active" not in (result.error or "")

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
        with patch(
            "app.application.integration.sync.orchestrator.PaginationIterator",
            side_effect=IntegrationApiException("offline", status_code=404),
        ):
            result = await orchestrator.sync_connection("conn1")
        assert result.entity_results[0].entity_type == "unknown"
        assert result.entity_results[0].errors

    @pytest.mark.asyncio
    async def test_sync_no_list_path(self, orchestrator, connection):
        connection.entity_mappings[0].list_path = None
        connection.encrypted_credentials = None
        result = await orchestrator.sync_connection("conn1")
        assert result.status == "error"
        assert "no data was fetched" in (result.error or "")

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

    @pytest.mark.asyncio
    async def test_item_with_missing_optional_required_field_is_still_upserted(self, orchestrator, connection):
        from app.infrastructure.http.pagination import PagePayload

        field_mappings = [
            FieldMapping(source="name", target="title"),
            FieldMapping(source="price", target="price"),
            FieldMapping(source="categoryId", target="category_id", required=True),
        ]
        entity_mapping = EntityMapping(
            entity_type="product",
            list_path="/products.json",
            list_method="GET",
            id_field="id",
            pagination=PaginationConfig(style=PaginationStyle.NONE),
            field_mappings=field_mappings,
        )
        writer = AsyncMock(spec=ProductWriter)
        writer.upsert = AsyncMock(return_value=True)
        entity_result = EntitySyncResult("product")
        page = PagePayload(data=[{"id": 23, "name": "Sunglasses Retro", "price": 30.0}], page_number=1, raw_response={})
        with patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer):
            await orchestrator._process_page(
                page=page,
                connection=connection,
                entity_mapping=entity_mapping,
                entity_result=entity_result,
                writer=writer,
            )
        assert entity_result.total_upserted == 1
        assert entity_result.total_mapped == 1
        assert any("record kept" in e for e in entity_result.errors)
        upserted_data = writer.upsert.await_args.kwargs["data"]
        assert upserted_data["title"] == "Sunglasses Retro"


class TestSyncNowAuthModes:
    """Token mode, public-data fallback mode and per-entity 401 skip behavior."""

    @pytest.fixture
    def connection(self):
        product_mapping = EntityMapping(
            entity_type="product",
            list_path="/api/Products",
            list_method="GET",
            id_field="id",
            pagination=PaginationConfig(style=PaginationStyle.NONE),
            field_mappings=[
                FieldMapping(source="name", target="title"),
                FieldMapping(source="price", target="price"),
            ],
        )
        customer_mapping = EntityMapping(
            entity_type="customer",
            list_path="/api/Customers",
            list_method="GET",
            id_field="id",
            pagination=PaginationConfig(style=PaginationStyle.NONE),
            field_mappings=[FieldMapping(source="email", target="email")],
        )
        return IntegrationConnection(
            id="conn1",
            store_id="s1",
            organization_id="o1",
            name="E-Commerce",
            platform_name="ecommerce",
            status=ConnectionStatus.INACTIVE,
            auth_config=AuthConfig(type="apiKey", name="X-API-Key"),
            encrypted_credentials="encrypted_key",
            entity_mappings=[product_mapping, customer_mapping],
            discovered_endpoints=[{"server": "https://93.184.216.34"}],
        )

    @pytest.fixture
    def mock_repo(self, connection):
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=connection)
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def llm_mapper(self):
        mapper = AsyncMock()
        mapper.build_entity_mapping = AsyncMock(return_value=None)
        return mapper

    @pytest.fixture
    def orchestrator(self, mock_repo, llm_mapper):
        return SyncOrchestrator(
            repository=mock_repo,
            llm_mapper=llm_mapper,
            vector_sync_enabled=False,
        )

    @pytest.fixture
    def writer(self):
        writer = AsyncMock(spec=ProductWriter)
        writer.upsert = AsyncMock(return_value=True)
        return writer

    @pytest.mark.asyncio
    async def test_token_mode_skips_401_entity_and_syncs_others(self, orchestrator, writer):
        page = PagePayload(
            data=[{"id": 7, "name": "Chair", "price": 49.9}],
            page_number=1,
            raw_response={},
        )
        public_paginator = FakePagination(pages=[page])
        protected_paginator = FakePagination(
            exc=IntegrationApiException("HTTP 401 from /api/Customers — expected a JSON API.", status_code=401)
        )
        with (
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[public_paginator, protected_paginator],
            ),
        ):
            result = await orchestrator.sync_connection("conn1", auth_token="ecomm-token")

        assert result.status == "completed"
        entities = {r.entity_type: r for r in result.entity_results}
        assert entities["product"].total_upserted == 1
        assert entities["product"].total_fetched == 1
        assert any("Skipped" in e and "401" in e for e in entities["customer"].errors)
        assert entities["customer"].total_fetched == 0

    @pytest.mark.asyncio
    async def test_public_fallback_stores_public_and_skips_protected(self, orchestrator, writer):
        page = PagePayload(
            data=[{"id": 3, "name": "Cup", "price": 4.5}],
            page_number=1,
            raw_response={},
        )
        public_paginator = FakePagination(pages=[page])
        protected_paginator = FakePagination(
            exc=IntegrationApiException("HTTP 403 from /api/Customers — expected a JSON API.", status_code=403)
        )
        with (
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[public_paginator, protected_paginator],
            ),
        ):
            result = await orchestrator.sync_connection("conn1", auth_token=None, public_fallback=True)

        assert result.status == "completed"
        entities = {r.entity_type: r for r in result.entity_results}
        assert entities["product"].total_upserted == 1
        assert any("Skipped" in e and "403" in e for e in entities["customer"].errors)

    @pytest.mark.asyncio
    async def test_all_entities_401_does_not_silently_succeed(self, orchestrator, writer):
        """REGRESSION: a deleted e-commerce account rejects every endpoint with
        401. The sync must surface this as a failure — not a "completed" result
        that the API returns as 200 while zero records are stored."""
        protected_paginator = FakePagination(
            exc=IntegrationApiException("HTTP 401 from /api/Products — expected a JSON API.", status_code=401)
        )
        with (
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[protected_paginator, protected_paginator],
            ),
        ):
            result = await orchestrator.sync_connection("conn1", auth_token="stale-token")

        assert result.status == "error", (
            f"All endpoints rejected with 401 but sync reported '{result.status}' — "
            "the API would return 200 while fetching nothing (deleted-account bug)."
        )
        assert result.error is not None
        entities = {r.entity_type: r for r in result.entity_results}
        assert entities["product"].total_fetched == 0
        assert entities["customer"].total_fetched == 0

    @pytest.mark.asyncio
    async def test_empty_200_without_errors_is_no_data_not_error(self, orchestrator, connection, mock_repo):
        """A legitimately empty store (200 + empty arrays, no errors) must stay
        'completed' with a no_data marker — it is not a failure."""
        connection.encrypted_credentials = None
        connection.status = ConnectionStatus.INACTIVE
        with patch(
            "app.application.integration.sync.orchestrator.PaginationIterator",
            side_effect=[FakePagination(), FakePagination()],
        ):
            result = await orchestrator.sync_connection("conn1")

        assert result.status == "completed"
        assert result.error is None
        assert connection.last_sync_status == "no_data"

    @pytest.mark.asyncio
    async def test_public_fallback_client_is_unauthenticated(self, orchestrator):
        empty = FakePagination()
        with (
            patch("app.application.integration.sync.orchestrator.ExternalApiClient") as mock_client_cls,
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[empty, empty],
            ),
        ):
            mock_client_cls.return_value = AsyncMock()
            await orchestrator.sync_connection("conn1", auth_token=None, public_fallback=True)

        _, kwargs = mock_client_cls.call_args
        assert kwargs["auth_config"] is None
        assert kwargs["encrypted_credentials"] is None

    @pytest.mark.asyncio
    async def test_token_client_uses_ephemeral_bearer_and_never_persists(self, orchestrator, connection):
        empty = FakePagination()
        with (
            patch("app.application.integration.sync.orchestrator.ExternalApiClient") as mock_client_cls,
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[empty, empty],
            ),
        ):
            mock_client_cls.return_value = AsyncMock()
            await orchestrator.sync_connection("conn1", auth_token="ecomm-token")

        _, kwargs = mock_client_cls.call_args
        assert kwargs["auth_config"].type == AuthType.BEARER
        assert kwargs["encrypted_credentials"] == '{"token": "ecomm-token"}'
        assert connection.encrypted_credentials == "encrypted_key"

    @pytest.mark.asyncio
    async def test_token_mode_persists_promo_capability(self, orchestrator):
        empty = FakePagination()
        with (
            patch("app.application.integration.sync.orchestrator.StoreCapabilitiesMongoRepository") as mock_caps,
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=AsyncMock()),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[empty, empty],
            ),
        ):
            mock_caps.return_value = AsyncMock()
            await orchestrator.sync_connection("conn1", auth_token="ecomm-token")

        mock_caps.return_value.update_capability.assert_awaited_once_with(
            "s1",
            "has_promo_codes",
            False,
            is_manual=False,
        )

    @pytest.mark.asyncio
    async def test_public_fallback_does_not_persist_capability(self, orchestrator):
        empty = FakePagination()
        with (
            patch("app.application.integration.sync.orchestrator.StoreCapabilitiesMongoRepository") as mock_caps,
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=AsyncMock()),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[empty, empty],
            ),
        ):
            mock_caps.return_value = AsyncMock()
            await orchestrator.sync_connection("conn1", auth_token=None, public_fallback=True)

        mock_caps.return_value.update_capability.assert_not_called()


OPENAPI_SPEC_WITH_PRODUCTS = {
    "openapi": "3.0.0",
    "info": {"title": "E-Commerce API", "version": "1.0.0"},
    "servers": [{"url": "https://93.184.216.34"}],
    "paths": {
        "/api/Products": {
            "get": {
                "operationId": "getProducts",
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Product"},
                            }
                        },
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Product": {
                "type": "object",
                "required": ["id", "name", "price"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                },
            }
        }
    },
}


class TestSyncSelfHealsEmptyMappings:
    """REGRESSION: connections created without entity mappings (older code or
    callers that never persisted them) must not fail forever with "No entity
    mappings configured." — the sync derives mappings from the raw spec."""

    @pytest.fixture
    def connection(self):
        return IntegrationConnection(
            id="conn-stale",
            store_id="s1",
            organization_id="o1",
            name="E-Commerce",
            platform_name="ecommerce",
            status=ConnectionStatus.INACTIVE,
            auth_config=AuthConfig(type="apiKey", name="X-API-Key"),
            encrypted_credentials="encrypted_key",
            entity_mappings=[],
            raw_spec=OPENAPI_SPEC_WITH_PRODUCTS,
            discovered_endpoints=[{"server": "https://93.184.216.34"}],
        )

    @pytest.fixture
    def mock_repo(self, connection):
        repo = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=connection)
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def orchestrator(self, mock_repo):
        return SyncOrchestrator(repository=mock_repo, vector_sync_enabled=False)

    @pytest.mark.asyncio
    async def test_sync_derives_and_persists_mappings_from_raw_spec(self, orchestrator, connection, mock_repo):
        page = PagePayload(
            data=[{"id": 1, "name": "Shirt", "price": 19.9}],
            page_number=1,
            raw_response={},
        )
        writer = AsyncMock(spec=ProductWriter)
        writer.upsert = AsyncMock(return_value=True)
        with (
            patch("app.application.integration.sync.orchestrator.get_writer", return_value=writer),
            patch(
                "app.application.integration.sync.orchestrator.PaginationIterator",
                side_effect=[FakePagination(pages=[page])],
            ),
        ):
            result = await orchestrator.sync_connection("conn-stale", auth_token="ecomm-token")

        assert result.status == "completed"
        assert result.error is None
        assert len(connection.entity_mappings) == 1
        assert connection.entity_mappings[0].entity_type == "product"
        assert connection.entity_mappings[0].list_path == "/api/Products"
        assert {f.source for f in connection.entity_mappings[0].field_mappings} >= {"name", "price"}
        assert result.entity_results[0].entity_type == "product"
        assert result.entity_results[0].total_upserted == 1
        assert result.entity_results[0].total_fetched == 1
        assert mock_repo.update.await_count >= 1

    @pytest.mark.asyncio
    async def test_sync_without_raw_spec_fails_with_actionable_error(self, orchestrator, connection):
        connection.raw_spec = None
        result = await orchestrator.sync_connection("conn-stale", auth_token="ecomm-token")
        assert result.status == "completed"
        assert "No entity mappings configured" in result.error
        assert "Re-run the full integration" in result.error
