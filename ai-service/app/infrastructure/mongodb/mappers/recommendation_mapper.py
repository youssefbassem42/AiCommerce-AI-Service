from app.domain.recommendation.entities.recommendation import Recommendation
from app.domain.recommendation.entities.bundle_suggestion import BundleSuggestion
from app.infrastructure.mongodb.documents.recommendation_document import RecommendationDocument
from app.infrastructure.mongodb.documents.bundle_document import BundleSuggestionDocument
from app.application.recommendation.dto.recommendation_dto import RecommendationDTO, BundleSuggestionDTO

class RecommendationMapper:
    """Maps Recommendation Aggregate between Mongo Documents, Domain Entities, and DTOs."""

    @staticmethod
    def to_entity(doc: RecommendationDocument) -> Recommendation:
        """Map Mongo Document to Domain Entity."""
        return doc.to_entity()

    @staticmethod
    def to_document(entity: Recommendation) -> RecommendationDocument:
        """Map Domain Entity to Mongo Document."""
        return RecommendationDocument.from_entity(entity)

    @staticmethod
    def to_dto(entity: Recommendation) -> RecommendationDTO:
        """Map Domain Entity to DTO."""
        return RecommendationDTO(
            id=entity.id,
            conversation_id=entity.conversation_id,
            customer_id=entity.customer_id,
            recommended_product_ids=entity.recommended_product_ids,
            store_id=entity.store_id,
            accepted=entity.accepted,
            rationale=entity.rationale,
            created_at=entity.created_at
        )

    @staticmethod
    def bundle_to_entity(doc: BundleSuggestionDocument) -> BundleSuggestion:
        """Map Bundle Document to Domain Entity."""
        return doc.to_entity()

    @staticmethod
    def bundle_to_document(entity: BundleSuggestion) -> BundleSuggestionDocument:
        """Map Bundle Domain Entity to Mongo Document."""
        return BundleSuggestionDocument.from_entity(entity)

    @staticmethod
    def bundle_to_dto(entity: BundleSuggestion) -> BundleSuggestionDTO:
        """Map Bundle Domain Entity to DTO."""
        return BundleSuggestionDTO(
            id=entity.id,
            store_id=entity.store_id,
            title=entity.title,
            product_ids=entity.product_ids,
            total_price=entity.total_price,
            discount_percentage=entity.discount_percentage,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
