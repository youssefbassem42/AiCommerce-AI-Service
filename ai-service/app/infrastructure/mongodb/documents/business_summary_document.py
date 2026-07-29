from typing import Any

from pydantic import Field

from app.domain.knowledge.entities.business_summary import BusinessSummary
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class BusinessSummaryDocument(BaseMongoDocument):
    """MongoDB document model representing a BusinessSummary."""

    document_id: str = Field(..., index=True)
    version_number: int = Field(default=1, ge=1)
    title: str = Field(...)
    summary: str = Field(...)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> BusinessSummary:
        return BusinessSummary(
            id=str(self.id),
            document_id=self.document_id,
            version_number=self.version_number,
            title=self.title,
            summary=self.summary,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: BusinessSummary) -> "BusinessSummaryDocument":
        return cls(
            _id=entity.id,
            document_id=entity.document_id,
            version_number=entity.version_number,
            title=entity.title,
            summary=entity.summary,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
