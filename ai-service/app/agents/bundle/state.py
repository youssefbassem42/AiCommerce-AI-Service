from typing import Any, TypedDict

from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
)
from app.domain.commerce.aggregates.product import Product


class BundleState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    budget: float | None
    desired_items: list[str]
    use_case: str | None
    budget_parsed: bool
    candidates_by_type: dict[str, list[Product]]
    bundles: list[BundleCandidate]
    selected: list[BundleCandidate]
    promo_code: str | None
    promo_status: str | None
    response: BundleResponse | None
    error: str | None
    store_capabilities: dict[str, bool] | None
    category_names: dict[str, str] | None
    shopping_state: dict[str, Any] | None
