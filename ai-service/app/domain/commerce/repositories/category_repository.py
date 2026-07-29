from abc import ABC, abstractmethod
from typing import Optional

from app.domain.commerce.aggregates.category import Category
from app.shared.kernel.repository import AsyncRepository


class CategoryRepository(AsyncRepository[Category, str], ABC):

    @abstractmethod
    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0) -> list[Category]:
        pass

    @abstractmethod
    async def find_children(self, parent_id: str) -> list[Category]:
        pass

    @abstractmethod
    async def find_root(self, store_id: str) -> list[Category]:
        pass
