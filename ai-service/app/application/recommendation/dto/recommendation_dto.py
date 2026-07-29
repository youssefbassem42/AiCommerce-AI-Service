from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class RecommendationDTO(BaseModel):
    id: str
    conversation_id: str
    customer_id: str
    recommended_product_ids: list[str]
    store_id: str
    accepted: bool
    rationale: str
    created_at: datetime


class BundleSuggestionDTO(BaseModel):
    id: str
    store_id: str
    title: str
    product_ids: list[str]
    total_price: float
    discount_percentage: float
    status: str
    created_at: datetime
    updated_at: datetime


class ProductSpecValue(BaseModel):
    name: str
    value: str
    category: str = "general"


class RecommendationIntent(BaseModel):
    product_type: str | None = None
    use_case: str | None = None
    required_specs: list[dict[str, str]] = Field(default_factory=list)
    max_budget: float | None = None
    min_quality: str | None = None
    hidden_needs: list[str] = Field(default_factory=list)


class ScoredProduct(BaseModel):
    product_id: str
    store_id: str
    title: str
    description: str | None = None
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: str | None = None
    product_url: str | None = None
    specs: list[ProductSpecValue] = Field(default_factory=list)
    match_score: float = 0.0
    match_reasons: list[str] = Field(default_factory=list)
    in_stock: bool = True
    score: float = 0.0


class ProductCard(BaseModel):
    product_id: str
    title: str
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: str | None = None
    product_url: str | None = None
    specs: list[ProductSpecValue] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    products: list[ProductCard] = Field(default_factory=list)
    rationale: str | None = None
    total_count: int = 0
    latency_ms: float = 0.0


class DiscountInfo(BaseModel):
    product_id: str
    product_title: str
    original_price: Decimal = Decimal("0")
    discount_pct: float = 0.0
    discount_amount: Decimal = Decimal("0")
    price_after_discount: Decimal = Decimal("0")


class BundleCandidate(BaseModel):
    products: list[DiscountInfo] = Field(default_factory=list)
    total_original: Decimal = Decimal("0")
    total_discount: Decimal = Decimal("0")
    total_after_discount: Decimal = Decimal("0")
    remaining_budget: float = 0.0
    within_budget: bool = True
    promo_code: str | None = None
    rank: int = 0


class BundleProductCard(BaseModel):
    product_id: str
    title: str
    original_price: Decimal = Decimal("0")
    discount_pct: float = 0.0
    discount_amount: Decimal = Decimal("0")
    final_price: Decimal = Decimal("0")
    image_url: str | None = None
    product_url: str | None = None


class BundleResponse(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    budget: float = 0.0
    bundles: list[BundleCandidate] = Field(default_factory=list)
    promo_code: str | None = None
    rationale: str | None = None
    latency_ms: float = 0.0
