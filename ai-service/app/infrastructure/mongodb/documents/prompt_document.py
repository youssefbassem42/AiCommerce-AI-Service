from datetime import UTC, datetime

from pydantic import Field

from app.domain.prompt.entities.prompt import Prompt
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class PromptDocument(BaseMongoDocument):
    key: str = Field(..., index=True, unique=True)
    type: str = Field(default="system")
    content: str = Field(...)
    description: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    is_active: bool = Field(default=True)
    variables: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_entity(self) -> Prompt:
        return Prompt(
            id=str(self.id),
            key=self.key,
            type=self.type,
            content=self.content,
            description=self.description,
            tags=self.tags,
            version=self.version,
            is_active=self.is_active,
            variables=self.variables,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: Prompt) -> "PromptDocument":
        return cls(
            _id=entity.id,
            key=entity.key,
            type=entity.type,
            content=entity.content,
            description=entity.description,
            tags=entity.tags,
            version=entity.version,
            is_active=entity.is_active,
            variables=entity.variables,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
