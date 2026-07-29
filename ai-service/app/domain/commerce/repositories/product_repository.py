from abc import ABC, abstractmethod
from typing import Optional

from app.domain.commerce.aggregates.product import Product
from app.shared.kernel.repository import AsyncRepository


class ProductRepository(AsyncRepository[Product, str], ABC):

    @abstractmethod
    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0) -> list[Product]:
        pass

    @abstractmethod
    async def find_by_external_id(self, store_id: str, external_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 20) -> list[Product]:
        pass
