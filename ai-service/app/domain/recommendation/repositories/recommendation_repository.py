from abc import ABC, abstractmethod
from typing import List
from app.shared.kernel.repository import AsyncRepository
from app.domain.recommendation.entities.recommendation import Recommendation
from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion

class RecommendationRepository(AsyncRepository[Recommendation, str], ABC):
    """Domain repository interface for Recommendation Aggregate."""

    @abstractmethod
    async def find_by_customer_id(self, customer_id: str, limit: int = 10) -> List[Recommendation]:
        """Get past recommendations for a customer."""
        pass

    @abstractmethod
    async def get_active_bundles(self, store_id: str) -> List[BundleSuggestion]:
        """Retrieve active product bundle suggestions for a store."""
        pass

    @abstractmethod
    async def save_bundle_suggestion(self, bundle: BundleSuggestion) -> BundleSuggestion:
        """Create or update a bundle suggestion."""
        pass
