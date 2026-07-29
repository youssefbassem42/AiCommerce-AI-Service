from datetime import datetime, UTC
from typing import List
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.recommendation.entities.recommendation import Recommendation

class RecommendationDocument(BaseMongoDocument):
    """MongoDB document model representing a Recommendation."""
    conversation_id: str = Field(..., index=True)
    customer_id: str = Field(..., index=True)
    recommended_product_ids: List[str] = Field(...)
    store_id: str = Field(..., index=True)
    accepted: bool = Field(...)
    rationale: str = Field(...)

    def to_entity(self) -> Recommendation:
        """Map document to domain Entity."""
        return Recommendation(
            id=str(self.id),
            conversation_id=self.conversation_id,
            customer_id=self.customer_id,
            recommended_product_ids=self.recommended_product_ids,
            store_id=self.store_id,
            accepted=self.accepted,
            rationale=self.rationale,
            created_at=self.created_at
        )

    @classmethod
    def from_entity(cls, entity: Recommendation) -> "RecommendationDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            conversation_id=entity.conversation_id,
            customer_id=entity.customer_id,
            recommended_product_ids=entity.recommended_product_ids,
            store_id=entity.store_id,
            accepted=entity.accepted,
            rationale=entity.rationale,
            created_at=entity.created_at
        )
