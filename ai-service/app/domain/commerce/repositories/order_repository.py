from abc import ABC, abstractmethod

from app.domain.commerce.aggregates.order import Order
from app.shared.kernel.repository import AsyncRepository


class OrderRepository(AsyncRepository[Order, str], ABC):

    @abstractmethod
    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0) -> list[Order]:
        pass

    @abstractmethod
    async def find_by_customer(self, customer_id: str, limit: int = 20, skip: int = 0) -> list[Order]:
        pass
