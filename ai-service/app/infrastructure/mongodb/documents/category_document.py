from typing import Optional

from pydantic import Field

from app.domain.commerce.aggregates.category import Category
from app.domain.commerce.value_objects.audit import AuditInfo
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.product_document import AuditInfoModel


class CategoryDocument(BaseMongoDocument):
    store_id: str = Field(..., index=True)
    org_id: str = Field(...)
    external_id: Optional[str] = None
    name: str = Field(...)
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0
    product_count: int = 0
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)

    def to_entity(self) -> Category:
        return Category(
            id=str(self.id),
            store_id=self.store_id,
            org_id=self.org_id,
            external_id=self.external_id,
            name=self.name,
            description=self.description,
            handle=self.handle,
            parent_id=self.parent_id,
            image_url=self.image_url,
            sort_order=self.sort_order,
            product_count=self.product_count,
            audit=self.audit.to_vo(),
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: Category) -> "CategoryDocument":
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            name=entity.name,
            description=entity.description,
            handle=entity.handle,
            parent_id=entity.parent_id,
            image_url=entity.image_url,
            sort_order=entity.sort_order,
            product_count=entity.product_count,
            audit=AuditInfoModel.from_vo(entity.audit),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
