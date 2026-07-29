from unittest.mock import AsyncMock

import pytest

from app.application.commerce.dto.commerce_dto import (
    InventoryCreateDTO,
    InventoryUpdateDTO,
)
from app.application.commerce.services import InventoryService
from app.domain.commerce.entities.inventory import Inventory
from app.domain.commerce.exceptions import InventoryNotFoundException


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.find_by_variant = AsyncMock()
    repo.find_many = AsyncMock()
    repo.paginate = AsyncMock()
    repo.find_low_stock = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    return InventoryService(repository=mock_repo)


class TestInventoryService:

    async def test_create_inventory(self, service, mock_repo):
        data = InventoryCreateDTO(
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            quantity=100,
            available=80,
        )
        mock_repo.create.return_value = Inventory(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            quantity=100,
            available=80,
        )
        result = await service.create(data)
        assert result.product_id == "p1"
        assert result.quantity == 100

    async def test_get_by_variant_found(self, service, mock_repo):
        mock_repo.find_by_variant.return_value = Inventory(
            id="i1", product_id="p1", variant_id="v1", store_id="s1", org_id="o1"
        )
        result = await service.get_by_variant("s1", "v1")
        assert result.variant_id == "v1"

    async def test_get_by_variant_not_found(self, service, mock_repo):
        mock_repo.find_by_variant.return_value = None
        with pytest.raises(InventoryNotFoundException):
            await service.get_by_variant("s1", "v99")

    async def test_update_inventory(self, service, mock_repo):
        existing = Inventory(
            id="i1", product_id="p1", variant_id="v1", store_id="s1", org_id="o1", quantity=50
        )
        mock_repo.find_many.return_value = [existing]
        mock_repo.update.return_value = Inventory(
            id="i1", product_id="p1", variant_id="v1", store_id="s1", org_id="o1", quantity=100
        )
        result = await service.update("v1", InventoryUpdateDTO(quantity=100))
        assert result.quantity == 100

    async def test_update_inventory_not_found(self, service, mock_repo):
        mock_repo.find_many.return_value = []
        with pytest.raises(InventoryNotFoundException):
            await service.update("v99", InventoryUpdateDTO(quantity=10))

    async def test_get_low_stock(self, service, mock_repo):
        mock_repo.find_low_stock.return_value = [
            Inventory(id="i1", product_id="p1", variant_id="v1", store_id="s1", org_id="o1", available=5)
        ]
        result = await service.get_low_stock("s1", threshold=10)
        assert len(result) == 1
        assert result[0].available == 5

    async def test_list_inventory(self, service, mock_repo):
        mock_repo.paginate.return_value = (
            [Inventory(id="i1", product_id="p1", variant_id="v1", store_id="s1", org_id="o1")],
            1,
        )
        result = await service.list(store_id="s1")
        assert result.total == 1
