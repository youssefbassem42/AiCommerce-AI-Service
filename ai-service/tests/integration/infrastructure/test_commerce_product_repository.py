from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.commerce.aggregates.product import Product
from app.infrastructure.mongodb.repositories.commerce_product_repository import (
    CommerceProductRepository,
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
    with patch("app.infrastructure.mongodb.repositories.commerce_product_repository.get_products_collection", return_value=mock_collection):
        r = CommerceProductRepository()
        r.collection = mock_collection
        return r


_now = datetime.now(UTC)
_base_doc = {
    "_id": "507f1f77bcf86cd799439011",
    "store_id": "store1",
    "organization_id": "org1",
    "external_id": None,
    "title": "Test Product",
    "description": None,
    "handle": None,
    "status": "draft",
    "product_type": None,
    "vendor": None,
    "tags": [],
    "images": [],
    "variants": [],
    "options": [],
    "seo": {"title": None, "description": None, "url_slug": None},
    "audit": {"created_at": _now, "updated_at": _now, "updated_by": None},
    "metadata": {},
    "category_id": None,
    "created_at": _now,
    "updated_at": _now,
    "deleted_at": None,
}


class TestCommerceProductRepository:

    async def test_create_product(self, repo, mock_collection):
        product = Product(
            id="507f1f77bcf86cd799439011",
            store_id="store1",
            organization_id="org1",
            title="Test",
        )
        result = await repo.create(product)
        assert result.id == product.id
        mock_collection.insert_one.assert_awaited_once()

    async def test_find_by_id(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=_base_doc.copy())
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is not None
        assert result.title == "Test Product"

    async def test_find_by_id_not_found(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=None)
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is None

    async def test_find_by_store(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_store("store1")
        assert len(result) == 1
        assert result[0].title == "Test Product"

    async def test_delete_product(self, repo, mock_collection):
        mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        result = await repo.delete("507f1f77bcf86cd799439011")
        assert result is True

    async def test_delete_product_not_found(self, repo, mock_collection):
        mock_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))
        result = await repo.delete("507f1f77bcf86cd799439011")
        assert result is False

    async def test_paginate(self, repo, mock_collection):
        mock_collection.count_documents = AsyncMock(return_value=1)
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        items, total = await repo.paginate({"store_id": "store1"})
        assert total == 1
        assert len(items) == 1

    async def test_find_by_external_id(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_external_id("store1", "ext-1")
        assert result is not None
        assert result.title == "Test Product"

    async def test_find_by_external_id_not_found(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([])
        result = await repo.find_by_external_id("store1", "ext-1")
        assert result is None
