from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.commerce.aggregates.category import Category
from app.infrastructure.mongodb.repositories.commerce_category_repository import (
    CommerceCategoryRepository,
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
    with patch("app.infrastructure.mongodb.repositories.commerce_category_repository.get_categories_collection", return_value=mock_collection):
        r = CommerceCategoryRepository()
        r.collection = mock_collection
        return r


_now = datetime.now(UTC)
_base_doc = {
    "_id": "507f1f77bcf86cd799439011",
    "store_id": "s1",
    "org_id": "o1",
    "external_id": None,
    "name": "Test Category",
    "description": None,
    "handle": None,
    "parent_id": None,
    "image_url": None,
    "sort_order": 0,
    "product_count": 0,
    "audit": {"created_at": _now, "updated_at": _now, "updated_by": None},
    "created_at": _now,
    "updated_at": _now,
    "deleted_at": None,
}


class TestCommerceCategoryRepository:

    async def test_create_category(self, repo, mock_collection):
        cat = Category(id="507f1f77bcf86cd799439011", store_id="s1", org_id="o1", name="Test")
        result = await repo.create(cat)
        assert result.id == cat.id
        mock_collection.insert_one.assert_awaited_once()

    async def test_find_root(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_root("s1")
        assert len(result) == 1

    async def test_find_children(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_children("parent1")
        assert len(result) == 1

    async def test_find_by_store(self, repo, mock_collection):
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        result = await repo.find_by_store("s1")
        assert len(result) == 1

    async def test_find_by_id(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=_base_doc.copy())
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is not None
        assert result.name == "Test Category"

    async def test_find_by_id_not_found(self, repo, mock_collection):
        mock_collection.find_one = AsyncMock(return_value=None)
        result = await repo.find_by_id("507f1f77bcf86cd799439011")
        assert result is None

    async def test_paginate(self, repo, mock_collection):
        mock_collection.count_documents = AsyncMock(return_value=1)
        mock_collection.find.return_value = _make_cursor([_base_doc.copy()])
        items, total = await repo.paginate({"store_id": "s1"})
        assert total == 1
        assert len(items) == 1
