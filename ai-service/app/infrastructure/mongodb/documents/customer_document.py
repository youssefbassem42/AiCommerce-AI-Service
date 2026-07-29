from typing import Any, Optional

from pydantic import Field

from app.domain.customer.entities.customer import Customer
from app.domain.commerce.value_objects.audit import AuditInfo
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.product_document import AuditInfoModel


class CustomerDocument(BaseMongoDocument):
    store_id: str = Field(..., index=True)
    organization_id: str = Field(...)
    external_id: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    accepts_marketing: bool = False
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> Customer:
        return Customer(
            id=str(self.id),
            store_id=self.store_id,
            organization_id=self.organization_id,
            external_id=self.external_id,
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            phone=self.phone,
            tags=self.tags,
            notes=self.notes,
            accepts_marketing=self.accepts_marketing,
            audit=self.audit.to_vo(),
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: Customer) -> "CustomerDocument":
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            external_id=entity.external_id,
            email=entity.email,
            first_name=entity.first_name,
            last_name=entity.last_name,
            phone=entity.phone,
            tags=entity.tags,
            notes=entity.notes,
            accepts_marketing=entity.accepts_marketing,
            audit=AuditInfoModel.from_vo(entity.audit),
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
