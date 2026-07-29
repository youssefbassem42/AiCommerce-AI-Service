from abc import ABC, abstractmethod
from typing import Optional

from app.domain.commerce.entities.inventory import Inventory
from app.shared.kernel.repository import AsyncRepository


class InventoryRepository(AsyncRepository[Inventory, str], ABC):

    @abstractmethod
    async def find_by_variant(self, store_id: str, variant_id: str) -> Optional[Inventory]:
        pass

    @abstractmethod
    async def find_low_stock(self, store_id: str, threshold: int = 10) -> list[Inventory]:
        pass
