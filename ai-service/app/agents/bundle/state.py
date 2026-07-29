from typing import Dict, List, Optional, TypedDict

from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
)
from app.domain.commerce.aggregates.product import Product


class BundleState(TypedDict):
    user_query: str
    store_id: str
    customer_id: Optional[str]
    budget: Optional[float]
    desired_items: List[str]
    budget_parsed: bool
    candidates_by_type: Dict[str, List[Product]]
    bundles: List[BundleCandidate]
    selected: List[BundleCandidate]
    promo_code: Optional[str]
    response: Optional[BundleResponse]
    error: Optional[str]
    store_capabilities: Optional[Dict[str, bool]]
