from unittest.mock import AsyncMock

import pytest

from app.application.commerce.dto.commerce_dto import CategoryCreateDTO, CategoryUpdateDTO
from app.application.commerce.services import CategoryService
from app.domain.commerce.aggregates.category import Category
from app.domain.commerce.exceptions import CategoryNotFoundException


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.paginate = AsyncMock()
    repo.find_children = AsyncMock()
    repo.find_root = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    return CategoryService(repository=mock_repo)


class TestCategoryService:

    async def test_create_category(self, service, mock_repo):
        data = CategoryCreateDTO(
            store_id="store1",
            org_id="org1",
            name="Electronics",
        )
        mock_repo.create.return_value = Category(
            id="c1",
            store_id="store1",
            org_id="org1",
            name="Electronics",
        )
        result = await service.create(data)
        assert result.name == "Electronics"

    async def test_get_category_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = Category(
            id="c1", store_id="s1", org_id="o1", name="Test"
        )
        result = await service.get_by_id("c1")
        assert result.name == "Test"

    async def test_get_category_not_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(CategoryNotFoundException):
            await service.get_by_id("nonexistent")

    async def test_list_categories(self, service, mock_repo):
        mock_repo.paginate.return_value = (
            [Category(id="c1", store_id="s1", org_id="o1", name="C1")],
            1,
        )
        result = await service.list(store_id="s1")
        assert result.total == 1

    async def test_update_category(self, service, mock_repo):
        existing = Category(id="c1", store_id="s1", org_id="o1", name="Old")
        mock_repo.find_by_id.return_value = existing
        mock_repo.update.return_value = Category(
            id="c1", store_id="s1", org_id="o1", name="Updated"
        )
        result = await service.update("c1", CategoryUpdateDTO(name="Updated"))
        assert result.name == "Updated"

    async def test_get_children(self, service, mock_repo):
        mock_repo.find_children.return_value = [
            Category(id="c2", store_id="s1", org_id="o1", name="Child", parent_id="c1")
        ]
        result = await service.get_children("c1")
        assert len(result) == 1
        assert result[0].name == "Child"

    async def test_get_root_categories(self, service, mock_repo):
        mock_repo.find_root.return_value = [
            Category(id="c1", store_id="s1", org_id="o1", name="Root")
        ]
        result = await service.get_root_categories("s1")
        assert len(result) == 1
        assert result[0].name == "Root"

    async def test_delete_category(self, service, mock_repo):
        mock_repo.delete.return_value = True
        result = await service.delete("c1")
        assert result is True

    async def test_delete_category_not_found(self, service, mock_repo):
        mock_repo.delete.return_value = False
        with pytest.raises(CategoryNotFoundException):
            await service.delete("nonexistent")
