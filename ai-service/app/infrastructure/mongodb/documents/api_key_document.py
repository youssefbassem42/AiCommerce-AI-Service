from datetime import datetime
from typing import Optional

from pydantic import Field

from app.domain.auth.entities.api_key import ApiKey
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class ApiKeyDocument(BaseMongoDocument):
    """MongoDB document model representing an ApiKey."""

    key_hash: str = Field(...)
    key_prefix: str = Field(..., index=True)
    name: str = Field(...)
    store_id: str = Field(..., index=True)
    scopes: list[str] = Field(default_factory=list)
    is_active: bool = Field(default=True, index=True)
    expires_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(...)
    deleted_at: Optional[datetime] = Field(default=None)

    def to_entity(self) -> ApiKey:
        return ApiKey(
            id=str(self.id),
            key_hash=self.key_hash,
            key_prefix=self.key_prefix,
            name=self.name,
            store_id=self.store_id,
            scopes=self.scopes,
            is_active=self.is_active,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: ApiKey) -> "ApiKeyDocument":
        return cls(
            _id=entity.id,
            key_hash=entity.key_hash,
            key_prefix=entity.key_prefix,
            name=entity.name,
            store_id=entity.store_id,
            scopes=entity.scopes,
            is_active=entity.is_active,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
