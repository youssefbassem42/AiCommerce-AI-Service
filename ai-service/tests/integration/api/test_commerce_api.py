from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

import pytest
from fastapi.testclient import TestClient

from app.api.commerce.dependencies import (
    get_category_service,
    get_inventory_service,
    get_order_service,
    get_product_service,
)
from app.application.commerce.dto.commerce_dto import (
    AuditInfoDTO,
    CategoryDTO,
    InventoryDTO,
    OrderDTO,
    ProductDTO,
)
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_product_service():
    service = MagicMock()
    service.create = AsyncMock()
    service.get_by_id = AsyncMock()
    service.list = AsyncMock()
    service.update = AsyncMock()
    service.delete = AsyncMock()
    return service


@pytest.fixture
def mock_category_service():
    service = MagicMock()
    service.create = AsyncMock()
    service.get_by_id = AsyncMock()
    service.list = AsyncMock()
    service.update = AsyncMock()
    service.delete = AsyncMock()
    service.get_children = AsyncMock()
    service.get_root_categories = AsyncMock()
    return service


@pytest.fixture
def mock_order_service():
    service = MagicMock()
    service.create = AsyncMock()
    service.get_by_id = AsyncMock()
    service.list = AsyncMock()
    service.update_status = AsyncMock()
    service.delete = AsyncMock()
    return service


@pytest.fixture
def mock_inventory_service():
    service = MagicMock()
    service.create = AsyncMock()
    service.get_by_variant = AsyncMock()
    service.list = AsyncMock()
    service.update = AsyncMock()
    service.get_low_stock = AsyncMock()
    return service


def _clear_overrides():
    app.dependency_overrides.clear()


class TestProductAPI:

    def test_create_product(self, client, mock_product_service):
        _clear_overrides()
        app.dependency_overrides[get_product_service] = lambda: mock_product_service

        now = datetime.now(UTC)
        mock_product_service.create.return_value = ProductDTO(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Test Product",
            status="draft",
            tags=[],
            images=[],
            variants=[],
            options=[],
            seo={"title": None, "description": None, "url_slug": None},
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            metadata={},
            created_at=now,
            updated_at=now,
        )

        response = client.post("/api/v1/commerce/products", json={
            "store_id": "store1",
            "organization_id": "org1",
            "title": "Test Product",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Product"
        assert data["store_id"] == "store1"
        _clear_overrides()

    def test_get_product(self, client, mock_product_service):
        _clear_overrides()
        app.dependency_overrides[get_product_service] = lambda: mock_product_service

        now = datetime.now(UTC)
        mock_product_service.get_by_id.return_value = ProductDTO(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Found",
            status="active",
            tags=[],
            images=[],
            variants=[],
            options=[],
            seo={"title": None, "description": None, "url_slug": None},
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            metadata={},
            created_at=now,
            updated_at=now,
        )
        response = client.get("/api/v1/commerce/products/p1")
        assert response.status_code == 200
        assert response.json()["title"] == "Found"
        _clear_overrides()

    def test_get_product_not_found(self, client, mock_product_service):
        _clear_overrides()
        app.dependency_overrides[get_product_service] = lambda: mock_product_service
        from app.domain.commerce.exceptions import ProductNotFoundException
        mock_product_service.get_by_id.side_effect = ProductNotFoundException("not found")
        response = client.get("/api/v1/commerce/products/nonexistent")
        assert response.status_code == 404
        _clear_overrides()

    def test_list_products(self, client, mock_product_service):
        _clear_overrides()
        app.dependency_overrides[get_product_service] = lambda: mock_product_service

        from app.application.commerce.dto.commerce_dto import PaginatedResultDTO
        mock_product_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)
        response = client.get("/api/v1/commerce/products?store_id=store1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        _clear_overrides()

    def test_delete_product(self, client, mock_product_service):
        _clear_overrides()
        app.dependency_overrides[get_product_service] = lambda: mock_product_service
        mock_product_service.delete.return_value = True
        response = client.delete("/api/v1/commerce/products/p1")
        assert response.status_code == 200
        assert response.json()["success"] is True
        _clear_overrides()


class TestCategoryAPI:

    def test_create_category(self, client, mock_category_service):
        _clear_overrides()
        app.dependency_overrides[get_category_service] = lambda: mock_category_service

        now = datetime.now(UTC)
        mock_category_service.create.return_value = CategoryDTO(
            id="c1",
            store_id="store1",
            org_id="org1",
            name="Electronics",
            sort_order=0,
            product_count=0,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            created_at=now,
            updated_at=now,
        )
        response = client.post("/api/v1/commerce/categories", json={
            "store_id": "store1",
            "org_id": "org1",
            "name": "Electronics",
        })
        assert response.status_code == 201
        assert response.json()["name"] == "Electronics"
        _clear_overrides()

    def test_list_categories(self, client, mock_category_service):
        _clear_overrides()
        app.dependency_overrides[get_category_service] = lambda: mock_category_service

        from app.application.commerce.dto.commerce_dto import PaginatedResultDTO
        mock_category_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)
        response = client.get("/api/v1/commerce/categories")
        assert response.status_code == 200
        _clear_overrides()

    def test_get_category_children(self, client, mock_category_service):
        _clear_overrides()
        app.dependency_overrides[get_category_service] = lambda: mock_category_service
        mock_category_service.get_children.return_value = []
        response = client.get("/api/v1/commerce/categories/c1/children")
        assert response.status_code == 200
        assert response.json() == []
        _clear_overrides()

    def test_get_root_categories(self, client, mock_category_service):
        _clear_overrides()
        app.dependency_overrides[get_category_service] = lambda: mock_category_service
        mock_category_service.get_root_categories.return_value = []
        response = client.get("/api/v1/commerce/categories/root/store1")
        assert response.status_code == 200
        _clear_overrides()


class TestOrderAPI:

    def test_create_order(self, client, mock_order_service):
        _clear_overrides()
        app.dependency_overrides[get_order_service] = lambda: mock_order_service

        now = datetime.now(UTC)
        mock_order_service.create.return_value = OrderDTO(
            id="o1",
            store_id="store1",
            org_id="org1",
            financial_status="pending",
            fulfillment_status=None,
            currency="USD",
            notes=None,
            tags=[],
            cancelled_at=None,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            metadata={},
            created_at=now,
            updated_at=now,
            line_items=[],
        )
        response = client.post("/api/v1/commerce/orders", json={
            "store_id": "store1",
            "org_id": "org1",
        })
        assert response.status_code == 201
        assert response.json()["financial_status"] == "pending"
        _clear_overrides()

    def test_get_order(self, client, mock_order_service):
        _clear_overrides()
        app.dependency_overrides[get_order_service] = lambda: mock_order_service

        now = datetime.now(UTC)
        mock_order_service.get_by_id.return_value = OrderDTO(
            id="o1",
            store_id="store1",
            org_id="org1",
            financial_status="paid",
            fulfillment_status=None,
            currency="USD",
            notes=None,
            tags=[],
            cancelled_at=None,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            metadata={},
            created_at=now,
            updated_at=now,
            line_items=[],
        )
        response = client.get("/api/v1/commerce/orders/o1")
        assert response.status_code == 200
        _clear_overrides()

    def test_update_order_status(self, client, mock_order_service):
        _clear_overrides()
        app.dependency_overrides[get_order_service] = lambda: mock_order_service

        now = datetime.now(UTC)
        mock_order_service.update_status.return_value = OrderDTO(
            id="o1",
            store_id="store1",
            org_id="org1",
            financial_status="paid",
            fulfillment_status="fulfilled",
            currency="USD",
            notes=None,
            tags=[],
            cancelled_at=None,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            metadata={},
            created_at=now,
            updated_at=now,
            line_items=[],
        )
        response = client.put("/api/v1/commerce/orders/o1/status", json={
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
        })
        assert response.status_code == 200
        assert response.json()["financial_status"] == "paid"
        _clear_overrides()

    def test_list_orders(self, client, mock_order_service):
        _clear_overrides()
        app.dependency_overrides[get_order_service] = lambda: mock_order_service

        from app.application.commerce.dto.commerce_dto import PaginatedResultDTO
        mock_order_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)
        response = client.get("/api/v1/commerce/orders")
        assert response.status_code == 200
        _clear_overrides()


class TestInventoryAPI:

    def test_create_inventory(self, client, mock_inventory_service):
        _clear_overrides()
        app.dependency_overrides[get_inventory_service] = lambda: mock_inventory_service

        now = datetime.now(UTC)
        mock_inventory_service.create.return_value = InventoryDTO(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            quantity=100,
            available=80,
            committed=20,
            incoming=0,
            location_id=None,
            location_name=None,
            low_stock_threshold=None,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            created_at=now,
            updated_at=now,
        )
        response = client.post("/api/v1/commerce/inventory", json={
            "product_id": "p1",
            "variant_id": "v1",
            "store_id": "store1",
            "org_id": "org1",
            "quantity": 100,
            "available": 80,
            "committed": 20,
        })
        assert response.status_code == 201
        assert response.json()["quantity"] == 100
        _clear_overrides()

    def test_get_inventory(self, client, mock_inventory_service):
        _clear_overrides()
        app.dependency_overrides[get_inventory_service] = lambda: mock_inventory_service

        now = datetime.now(UTC)
        mock_inventory_service.get_by_variant.return_value = InventoryDTO(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            quantity=50,
            available=30,
            committed=20,
            incoming=5,
            location_id=None,
            location_name=None,
            low_stock_threshold=None,
            audit=AuditInfoDTO(created_at=now, updated_at=now),
            created_at=now,
            updated_at=now,
        )
        response = client.get("/api/v1/commerce/inventory/v1?store_id=store1")
        assert response.status_code == 200
        assert response.json()["variant_id"] == "v1"
        _clear_overrides()

    def test_get_low_stock(self, client, mock_inventory_service):
        _clear_overrides()
        app.dependency_overrides[get_inventory_service] = lambda: mock_inventory_service
        mock_inventory_service.get_low_stock.return_value = []
        response = client.get("/api/v1/commerce/inventory/low-stock/store1?threshold=5")
        assert response.status_code == 200
        _clear_overrides()
