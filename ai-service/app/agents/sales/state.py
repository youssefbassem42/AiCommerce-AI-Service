from typing import Any, TypedDict

from app.application.recommendation.dto.recommendation_dto import ProductCard
from app.application.recommendation.dto.sales_dto import SalesResponse


class SalesState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    conversation_id: str | None
    history: list[dict]
    stage: str
    customer_answers: dict
    products: list[ProductCard]
    offer: dict
    objection: dict | None
    promo_code: str | None
    checkout_note: str | None
    clarifying_question: str | None
    store_capabilities: dict
    context: dict[str, Any]
    response: SalesResponse | None
    error: str | None
