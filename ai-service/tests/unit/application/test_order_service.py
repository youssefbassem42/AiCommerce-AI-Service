from unittest.mock import AsyncMock

import pytest

from app.application.commerce.dto.commerce_dto import OrderCreateDTO, OrderUpdateDTO
from app.application.commerce.services import OrderService
from app.domain.commerce.aggregates.order import Order
from app.domain.commerce.exceptions import OrderNotFoundException


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
    return OrderService(repository=mock_repo)


class TestOrderService:

    async def test_create_order(self, service, mock_repo):
        data = OrderCreateDTO(
            store_id="store1",
            org_id="org1",
            customer_id="c1",
        )
        mock_repo.create.return_value = Order(
            id="o1",
            store_id="store1",
            org_id="org1",
            customer_id="c1",
        )
        result = await service.create(data)
        assert result.store_id == "store1"

    async def test_get_order_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = Order(
            id="o1", store_id="s1", org_id="o1"
        )
        result = await service.get_by_id("o1")
        assert result.id == "o1"

    async def test_get_order_not_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(OrderNotFoundException):
            await service.get_by_id("nonexistent")

    async def test_list_orders(self, service, mock_repo):
        mock_repo.paginate.return_value = (
            [Order(id="o1", store_id="s1", org_id="o1")],
            1,
        )
        result = await service.list(store_id="s1")
        assert result.total == 1

    async def test_update_order_status(self, service, mock_repo):
        existing = Order(id="o1", store_id="s1", org_id="o1", financial_status="pending")
        mock_repo.find_by_id.return_value = existing
        mock_repo.update.return_value = Order(
            id="o1", store_id="s1", org_id="o1", financial_status="paid"
        )
        result = await service.update_status("o1", OrderUpdateDTO(financial_status="paid"))
        assert result.financial_status == "paid"

    async def test_delete_order(self, service, mock_repo):
        mock_repo.delete.return_value = True
        result = await service.delete("o1")
        assert result is True

    async def test_delete_order_not_found(self, service, mock_repo):
        mock_repo.delete.return_value = False
        with pytest.raises(OrderNotFoundException):
            await service.delete("nonexistent")
