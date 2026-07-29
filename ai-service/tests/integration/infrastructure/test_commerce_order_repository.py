from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.commerce.aggregates.order import Order
from app.infrastructure.mongodb.repositories.commerce_order_repository import (
    CommerceOrderRepository,
)


def _make_cursor(data: list[dict]) -> MagicMock:
    cursor = MagicMock()
    cursor.__aiter__.return_value = iter(data)
    cursor.skip.return_value = cursor
    cursor.limit.return_value = cursor
    return cursor


@pytest.fixture
def mock_collection():
    col = MagicMock()
    col.find_one = AsyncMock()
    col.insert_one = AsyncMock()
    col.delete_one = AsyncMock()
    col.count_documents = AsyncMock()
    col.replace_one = AsyncMock()
    col.find = MagicMock()
    return col


@pytest.fixture
def repo(mock_collection):
    with patch("app.infrastructure.mongodb.repositories.commerce_order_repository.get_orders_collection", return_value=mock_collection):
        r = CommerceOrderRepository()
        r.collection = mock_collection
        return r


_now = datetime.now(UTC)
_base_doc = {
    "_id": "507f1f77bcf86cd799439011",
    "store_id": "s1",
    "org_id": "o1",
    "external_id": None,
    "customer_id": "c1",
    "customer_email": None,
    "line_items": [],
    "shipping_address": None,
    "billing_address": None,
    "subtotal_price": None,
    "total_price": None,
    "total_tax": None,
    "total_discount": None,
    "shipping_price": None,
    "financial_status": "pending",
    "fulfillment_status": None,
    "currency": "USD",
    "notes": None,
    "tags": [],
    "cancelled_at": None,
    "audit": {"created_at": _now, "updated_at": _now, "updated_by": None},
    "metadata": {},
    "created_at": _now,
    "updated_at": _now,
    "deleted_at": None,
}


class TestCommerceOrderRepository:

    async def test_create_order(self, repo, mock_collection):
        order = Order(id="507f1f77bcf86cd799439011", store_id="s1", org_id="o1")
        result = await repo.create(order)
        assert result.id == order.id
        mock_collection.insert_one.assert_awaited_once()

    async def test_find_by_store(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_store("s1")
        assert len(result) == 1

    async def test_find_by_customer(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_customer("c1")
        assert len(result) == 1

    async def test_find_by_id(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=_base_doc.copy())
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is not None
        assert result.store_id == "s1"

    async def test_find_by_id_not_found(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=None)
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is None
