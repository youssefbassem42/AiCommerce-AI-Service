from typing import List, Optional, TypedDict

from app.application.recommendation.dto.recommendation_dto import (
    ProductCard,
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)


class RecommendationState(TypedDict):
    user_query: str
    store_id: str
    customer_id: Optional[str]
    intent: Optional[RecommendationIntent]
    candidates: List[ScoredProduct]
    filtered: List[ScoredProduct]
    response: Optional[RecommendationResponse]
    error: Optional[str]
