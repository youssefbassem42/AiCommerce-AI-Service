from decimal import Decimal

from pydantic import BaseModel, Field


class RecommendationRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, description="User's product recommendation query")
    store_id: str = Field(..., min_length=1, description="Store ID to search in")
    customer_id: str | None = Field(None, description="Optional customer ID")


class ProductCardSchema(BaseModel):
    product_id: str
    title: str
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: str | None = None
    product_url: str | None = None
    specs: list[dict] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)


class RecommendationResponseSchema(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    products: list[ProductCardSchema] = Field(default_factory=list)
    rationale: str | None = None
    total_count: int = 0
    latency_ms: float = 0.0


class DiscountInfoSchema(BaseModel):
    product_id: str
    product_title: str
    original_price: str = "0"
    discount_pct: float = 0.0
    discount_amount: str = "0"
    price_after_discount: str = "0"


class BundleCandidateSchema(BaseModel):
    products: list[DiscountInfoSchema] = Field(default_factory=list)
    total_original: str = "0"
    total_discount: str = "0"
    total_after_discount: str = "0"
    remaining_budget: float = 0.0
    within_budget: bool = True
    promo_code: str | None = None
    rank: int = 0


class BundleRequestSchema(BaseModel):
    message: str = Field(
        ..., min_length=1, description="User's bundle request (e.g., 'I have $300 and want a monitor')"
    )
    store_id: str = Field(..., min_length=1, description="Store ID")
    customer_id: str | None = Field(None, description="Optional customer ID")


class BundleResponseSchema(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    budget: float = 0.0
    bundles: list[BundleCandidateSchema] = Field(default_factory=list)
    promo_code: str | None = None
    rationale: str | None = None
    latency_ms: float = 0.0
