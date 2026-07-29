from typing import Optional

from pydantic import Field

from app.domain.commerce.entities.inventory import Inventory
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.product_document import AuditInfoModel


class InventoryDocument(BaseMongoDocument):
    product_id: str = Field(...)
    variant_id: str = Field(...)
    store_id: str = Field(..., index=True)
    org_id: str = Field(...)
    external_id: Optional[str] = None
    quantity: int = 0
    available: int = 0
    committed: int = 0
    incoming: int = 0
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = None
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)

    def to_entity(self) -> Inventory:
        return Inventory(
            id=str(self.id),
            product_id=self.product_id,
            variant_id=self.variant_id,
            store_id=self.store_id,
            org_id=self.org_id,
            external_id=self.external_id,
            quantity=self.quantity,
            available=self.available,
            committed=self.committed,
            incoming=self.incoming,
            location_id=self.location_id,
            location_name=self.location_name,
            low_stock_threshold=self.low_stock_threshold,
            audit=self.audit.to_vo(),
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: Inventory) -> "InventoryDocument":
        return cls(
            _id=entity.id,
            product_id=entity.product_id,
            variant_id=entity.variant_id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            quantity=entity.quantity,
            available=entity.available,
            committed=entity.committed,
            incoming=entity.incoming,
            location_id=entity.location_id,
            location_name=entity.location_name,
            low_stock_threshold=entity.low_stock_threshold,
            audit=AuditInfoModel.from_vo(entity.audit),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
