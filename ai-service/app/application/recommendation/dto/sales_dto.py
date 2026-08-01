from pydantic import BaseModel, Field

from app.application.recommendation.dto.recommendation_dto import ProductCard


class SalesResponse(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    stage: str = "discovery"
    products: list[ProductCard] = Field(default_factory=list)
    offer: dict = Field(default_factory=dict)
    objection: dict | None = None
    promo_code: str | None = None
    checkout_note: str | None = None
    clarifying_question: str | None = None
    rationale: str | None = None
    latency_ms: float = 0.0
