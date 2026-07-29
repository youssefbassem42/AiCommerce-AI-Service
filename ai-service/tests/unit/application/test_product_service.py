from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.application.commerce.dto.commerce_dto import (
    MoneyDTO,
    ProductCreateDTO,
    ProductUpdateDTO,
    VariantDTO,
)
from app.application.commerce.services import ProductService
from app.domain.commerce.aggregates.product import Product
from app.domain.commerce.exceptions import ProductNotFoundException
from app.domain.commerce.value_objects.money import Money


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.paginate = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    return ProductService(repository=mock_repo)


class TestProductService:

    async def test_create_product(self, service, mock_repo):
        data = ProductCreateDTO(
            store_id="store1",
            organization_id="org1",
            title="Test Product",
            variants=[
                VariantDTO(
                    id="v1",
                    sku="SKU-001",
                    title="V1",
                    price=MoneyDTO(amount=Decimal("10"), currency="USD"),
                )
            ],
        )
        mock_repo.create.return_value = Product(
            id="new-id",
            store_id="store1",
            organization_id="org1",
            title="Test Product",
            status="draft",
            variants=[],
        )
        result = await service.create(data)
        assert result.title == "Test Product"
        assert result.store_id == "store1"
        mock_repo.create.assert_awaited_once()

    async def test_get_product_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Found",
        )
        result = await service.get_by_id("p1")
        assert result.title == "Found"

    async def test_get_product_not_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(ProductNotFoundException):
            await service.get_by_id("nonexistent")

    async def test_list_products(self, service, mock_repo):
        mock_repo.paginate.return_value = (
            [Product(id="p1", store_id="s1", organization_id="o1", title="P1")],
            1,
        )
        result = await service.list(page=1, page_size=20, store_id="s1")
        assert result.total == 1
        assert len(result.items) == 1

    async def test_list_products_empty(self, service, mock_repo):
        mock_repo.paginate.return_value = ([], 0)
        result = await service.list(page=1, page_size=20)
        assert result.total == 0
        assert result.items == []

    async def test_update_product(self, service, mock_repo):
        existing = Product(id="p1", store_id="s1", organization_id="o1", title="Old")
        mock_repo.find_by_id.return_value = existing
        mock_repo.update.return_value = Product(
            id="p1", store_id="s1", organization_id="o1", title="Updated"
        )
        data = ProductUpdateDTO(title="Updated")
        result = await service.update("p1", data)
        assert result.title == "Updated"

    async def test_update_product_not_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(ProductNotFoundException):
            await service.update("nonexistent", ProductUpdateDTO(title="New"))

    async def test_delete_product(self, service, mock_repo):
        mock_repo.delete.return_value = True
        result = await service.delete("p1")
        assert result is True

    async def test_delete_product_not_found(self, service, mock_repo):
        mock_repo.delete.return_value = False
        with pytest.raises(ProductNotFoundException):
            await service.delete("nonexistent")
