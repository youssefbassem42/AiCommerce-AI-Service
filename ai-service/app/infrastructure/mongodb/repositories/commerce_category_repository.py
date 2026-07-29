from typing import Any, Optional

from app.domain.commerce.aggregates.category import Category
from app.domain.commerce.repositories.category_repository import CategoryRepository as ICategoryRepository
from app.infrastructure.mongodb.collections import get_categories_collection
from app.infrastructure.mongodb.documents.category_document import CategoryDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class CommerceCategoryRepository(BaseMongoRepository[CategoryDocument, Category], ICategoryRepository):

    def __init__(self):
        super().__init__(get_categories_collection(), CategoryDocument)

    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0, session: Any = None) -> list[Category]:
        return await self.find_many({"store_id": store_id}, limit=limit, skip=skip, session=session)

    async def find_children(self, parent_id: str) -> list[Category]:
        return await self.find_many({"parent_id": parent_id})

    async def find_root(self, store_id: str) -> list[Category]:
        return await self.find_many({"store_id": store_id, "parent_id": None})
