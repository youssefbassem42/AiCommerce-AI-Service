from typing import TypedDict

from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)


class RecommendationState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    intent: RecommendationIntent | None
    candidates: list[ScoredProduct]
    filtered: list[ScoredProduct]
    response: RecommendationResponse | None
    error: str | None
