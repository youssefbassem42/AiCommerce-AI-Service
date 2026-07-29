from typing import Any, Optional

from app.domain.commerce.aggregates.product import Product
from app.domain.commerce.repositories.product_repository import ProductRepository as IProductRepository
from app.infrastructure.mongodb.collections import get_products_collection
from app.infrastructure.mongodb.documents.product_document import ProductDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class CommerceProductRepository(BaseMongoRepository[ProductDocument, Product], IProductRepository):

    def __init__(self):
        super().__init__(get_products_collection(), ProductDocument)

    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0, session: Any = None) -> list[Product]:
        return await self.find_many({"store_id": store_id}, limit=limit, skip=skip, session=session)

    async def find_by_external_id(self, store_id: str, external_id: str) -> Optional[Product]:
        products = await self.find_many({"store_id": store_id, "external_id": external_id}, limit=1)
        return products[0] if products else None

    async def search(self, query: str, limit: int = 20) -> list[Product]:
        return await self.find_many({"$text": {"$search": query}}, limit=limit)
