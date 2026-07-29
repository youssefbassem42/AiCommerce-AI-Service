from typing import Optional

from app.domain.customer.entities.customer import Customer
from app.shared.kernel.repository import AsyncRepository


class ICustomerRepository(AsyncRepository[Customer, str]):
    async def find_by_store(self, store_id: str, limit: int = 20, skip: int = 0) -> list[Customer]:
        ...

    async def find_by_email(self, store_id: str, email: str) -> Optional[Customer]:
        ...
