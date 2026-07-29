from datetime import datetime, UTC
from typing import List
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion

class BundleSuggestionDocument(BaseMongoDocument):
    """MongoDB document model representing a BundleSuggestion."""
    store_id: str = Field(..., index=True)
    title: str = Field(...)
    product_ids: List[str] = Field(...)
    total_price: float = Field(...)
    discount_percentage: float = Field(...)
    status: str = Field(default="active")

    def to_entity(self) -> BundleSuggestion:
        """Map document to domain Entity."""
        return BundleSuggestion(
            id=str(self.id),
            store_id=self.store_id,
            title=self.title,
            product_ids=self.product_ids,
            total_price=self.total_price,
            discount_percentage=self.discount_percentage,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_entity(cls, entity: BundleSuggestion) -> "BundleSuggestionDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            title=entity.title,
            product_ids=entity.product_ids,
            total_price=entity.total_price,
            discount_percentage=entity.discount_percentage,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
