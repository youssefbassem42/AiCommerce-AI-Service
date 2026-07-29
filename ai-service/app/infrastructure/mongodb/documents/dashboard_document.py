from datetime import datetime, UTC
from typing import Dict, Any, List
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.analytics.entities.dashboard_insight import DashboardInsight

class DashboardInsightDocument(BaseMongoDocument):
    """MongoDB document model representing a DashboardInsight."""
    store_id: str = Field(..., index=True)
    recommendations: List[str] = Field(...)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> DashboardInsight:
        """Map document to domain Entity."""
        return DashboardInsight(
            id=str(self.id),
            store_id=self.store_id,
            recommendations=self.recommendations,
            metadata=self.metadata,
            calculated_at=self.created_at
        )

    @classmethod
    def from_entity(cls, entity: DashboardInsight) -> "DashboardInsightDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            recommendations=entity.recommendations,
            metadata=entity.metadata,
            created_at=entity.calculated_at
        )
