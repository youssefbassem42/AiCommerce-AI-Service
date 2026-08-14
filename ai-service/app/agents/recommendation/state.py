from typing import Any, TypedDict

from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)


class RecommendationState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    shopping_state: dict[str, Any] | None
    intent: RecommendationIntent | None
    candidates: list[ScoredProduct]
    filtered: list[ScoredProduct]
    ranked: list[ScoredProduct]
    clarifying_question: str | None
    response: RecommendationResponse | None
    error: str | None
