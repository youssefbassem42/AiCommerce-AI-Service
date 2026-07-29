from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.integration.entities.data_entity import DataEntity
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class DataEntityDocument(BaseMongoDocument):
    store_id: str = Field(...)
    organization_id: str = Field(...)
    entity_type: str = Field(...)
    external_id: str = Field(...)
    data: dict[str, Any] = Field(default_factory=dict)
    connection_id: Optional[str] = None
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_entity(self) -> DataEntity:
        return DataEntity(
            id=str(self.id),
            store_id=self.store_id,
            organization_id=self.organization_id,
            entity_type=self.entity_type,
            external_id=self.external_id,
            data=self.data,
            connection_id=self.connection_id,
            synced_at=self.synced_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: DataEntity) -> "DataEntityDocument":
        kwargs: dict[str, Any] = {
            "store_id": entity.store_id,
            "organization_id": entity.organization_id,
            "entity_type": entity.entity_type,
            "external_id": entity.external_id,
            "data": entity.data,
            "connection_id": entity.connection_id,
            "synced_at": entity.synced_at,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
            "deleted_at": entity.deleted_at,
        }
        if entity.id:
            kwargs["_id"] = entity.id
        return cls(**kwargs)
