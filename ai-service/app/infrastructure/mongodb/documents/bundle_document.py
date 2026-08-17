from pydantic import Field

from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class BundleSuggestionDocument(BaseMongoDocument):
    """MongoDB document model representing a BundleSuggestion."""

    store_id: str = Field(..., index=True)
    title: str = Field(...)
    product_ids: list[str] = Field(...)
    total_price: float = Field(...)
    discount_percentage: float = Field(...)
    rank: int = Field(default=1, description="Selection rank of the bundle (1 = the presented bundle, B17)")
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
            rank=self.rank,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
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
            rank=entity.rank,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
