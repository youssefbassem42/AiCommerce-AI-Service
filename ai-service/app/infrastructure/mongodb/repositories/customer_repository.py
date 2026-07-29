from typing import Optional

from app.domain.customer.entities.customer import Customer
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.mongodb.collections import get_customers_collection
from app.infrastructure.mongodb.documents.customer_document import CustomerDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class CustomerMongoRepository(BaseMongoRepository[CustomerDocument, Customer], ICustomerRepository):
    def __init__(self) -> None:
        super().__init__(get_customers_collection(), CustomerDocument)

    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0) -> list[Customer]:
        return await self.find_many({"store_id": store_id}, limit=limit, skip=skip)

    async def find_by_email(self, store_id: str, email: str) -> Optional[Customer]:
        items = await self.find_many({"store_id": store_id, "email": email}, limit=1)
        return items[0] if items else None
