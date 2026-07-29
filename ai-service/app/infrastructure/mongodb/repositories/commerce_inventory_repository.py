from typing import Any, Optional

from app.domain.commerce.entities.inventory import Inventory
from app.domain.commerce.repositories.inventory_repository import InventoryRepository as IInventoryRepository
from app.infrastructure.mongodb.collections import get_inventory_collection
from app.infrastructure.mongodb.documents.inventory_document import InventoryDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class CommerceInventoryRepository(BaseMongoRepository[InventoryDocument, Inventory], IInventoryRepository):

    def __init__(self):
        super().__init__(get_inventory_collection(), InventoryDocument)

    async def find_by_variant(self, store_id: str, variant_id: str) -> Optional[Inventory]:
        items = await self.find_many({"store_id": store_id, "variant_id": variant_id}, limit=1)
        return items[0] if items else None

    async def find_low_stock(self, store_id: str, threshold: int = 10) -> list[Inventory]:
        return await self.find_many({"store_id": store_id, "available": {"$lte": threshold}})
