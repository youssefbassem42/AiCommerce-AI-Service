from typing import List, Any
from bson import ObjectId
import logging

from app.domain.recommendation.entities.recommendation import Recommendation
from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion
from app.domain.recommendation.repositories.recommendation_repository import RecommendationRepository as IRecommendationRepository
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.recommendation_document import RecommendationDocument
from app.infrastructure.mongodb.documents.bundle_document import BundleSuggestionDocument
from app.infrastructure.mongodb.collections import get_recommendations_collection, get_bundle_suggestions_collection

logger = logging.getLogger(__name__)

class RecommendationRepository(BaseMongoRepository[RecommendationDocument, Recommendation], IRecommendationRepository):
    """MongoDB implementation of the RecommendationRepository with session and transaction support."""

    def __init__(self):
        super().__init__(get_recommendations_collection(), RecommendationDocument)
        self.bundles_collection = get_bundle_suggestions_collection()

    async def find_by_customer_id(self, customer_id: str, limit: int = 10, session: Any = None) -> List[Recommendation]:
        """Fetch past recommendations for a customer."""
        try:
            return await self.find_many({"customer_id": customer_id}, limit=limit, session=session)
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def get_active_bundles(self, store_id: str, session: Any = None) -> List[BundleSuggestion]:
        """Retrieve active product bundle suggestions for a store."""
        try:
            cursor = self.bundles_collection.find(
                {"store_id": store_id, "status": "active"}, 
                session=session
            ).sort("created_at", -1)
            
            bundles = []
            async for data in cursor:
                doc = BundleSuggestionDocument.from_mongo_dict(data)
                bundles.append(doc.to_entity())
            return bundles
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def save_bundle_suggestion(self, bundle: BundleSuggestion, session: Any = None) -> BundleSuggestion:
        """Create or update a bundle suggestion."""
        if not ObjectId.is_valid(bundle.id):
            raise ValueError(f"Bundle contains an invalid ObjectId format: {bundle.id}")
        try:
            doc = BundleSuggestionDocument.from_entity(bundle)
            data = doc.to_mongo_dict()
            await self.bundles_collection.replace_one(
                {"_id": ObjectId(bundle.id)}, 
                data, 
                upsert=True, 
                session=session
            )
            return bundle
        except Exception as e:
            self._handle_db_error(e)
            raise
