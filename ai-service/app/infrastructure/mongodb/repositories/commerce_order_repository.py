from typing import Any, Optional

from app.domain.commerce.aggregates.order import Order
from app.domain.commerce.repositories.order_repository import OrderRepository as IOrderRepository
from app.infrastructure.mongodb.collections import get_orders_collection
from app.infrastructure.mongodb.documents.order_document import OrderDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class CommerceOrderRepository(BaseMongoRepository[OrderDocument, Order], IOrderRepository):

    def __init__(self):
        super().__init__(get_orders_collection(), OrderDocument)

    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0, session: Any = None) -> list[Order]:
        return await self.find_many({"store_id": store_id}, limit=limit, skip=skip, session=session)

    async def find_by_customer(self, customer_id: str, limit: int = 20, skip: int = 0) -> list[Order]:
        return await self.find_many({"customer_id": customer_id}, limit=limit, skip=skip)
