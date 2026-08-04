from datetime import datetime
from typing import Any

from pydantic import Field

from app.domain.memory.entities.user_memory import UserMemory
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class UserMemoryDocument(BaseMongoDocument):
    """MongoDB document model representing a UserMemory entry."""

    user_id: str = Field(..., index=True)
    store_id: str = Field(..., index=True)
    key: str = Field(...)
    value: dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int | None = Field(None)
    expires_at: datetime | None = Field(None, index=True)

    def to_entity(self) -> UserMemory:
        """Map document to domain Entity."""
        return UserMemory(
            id=str(self.id),
            user_id=self.user_id,
            store_id=self.store_id,
            key=self.key,
            value=self.value,
            ttl_seconds=self.ttl_seconds,
            expires_at=self.expires_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: UserMemory) -> "UserMemoryDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            user_id=entity.user_id,
            store_id=entity.store_id,
            key=entity.key,
            value=entity.value,
            ttl_seconds=entity.ttl_seconds,
            expires_at=entity.expires_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
