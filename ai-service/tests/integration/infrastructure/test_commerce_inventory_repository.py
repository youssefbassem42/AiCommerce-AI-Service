from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.commerce.entities.inventory import Inventory
from app.infrastructure.mongodb.repositories.commerce_inventory_repository import (
    CommerceInventoryRepository,
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
    with patch("app.infrastructure.mongodb.repositories.commerce_inventory_repository.get_inventory_collection", return_value=mock_collection):
        r = CommerceInventoryRepository()
        r.collection = mock_collection
        return r


_now = datetime.now(UTC)
_base_doc = {
    "_id": "507f1f77bcf86cd799439011",
    "product_id": "p1",
    "variant_id": "v1",
    "store_id": "s1",
    "org_id": "o1",
    "external_id": None,
    "quantity": 100,
    "available": 80,
    "committed": 20,
    "incoming": 0,
    "location_id": None,
    "location_name": None,
    "low_stock_threshold": None,
    "audit": {"created_at": _now, "updated_at": _now, "updated_by": None},
    "created_at": _now,
    "updated_at": _now,
    "deleted_at": None,
}


class TestCommerceInventoryRepository:

    async def test_create_inventory(self, repo, mock_collection):
        inv = Inventory(
            id="507f1f77bcf86cd799439011",
            product_id="p1",
            variant_id="v1",
            store_id="s1",
            org_id="o1",
        )
        result = await repo.create(inv)
        assert result.id == inv.id
        mock_collection.insert_one.assert_awaited_once()

    async def test_find_by_variant(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_variant("s1", "v1")
        assert result is not None
        assert result.variant_id == "v1"

    async def test_find_by_variant_not_found(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([])
        result = await repo.find_by_variant("s1", "v99")
        assert result is None

    async def test_find_low_stock(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_low_stock("s1", threshold=5)
        assert len(result) == 1

    async def test_find_by_id(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=_base_doc.copy())
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is not None
        assert result.product_id == "p1"

    async def test_delete(self, repo, mock_collection):
        mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        result = await repo.delete("507f1f77bcf86cd799439011")
        assert result is True
