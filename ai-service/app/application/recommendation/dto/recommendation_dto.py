from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AliasChoices, BaseModel, Field


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
    """Structured recommendation request (Fix 4.1).

    The LLM produces the canonical form
    (category, budget, currency, use_case, brand, attributes); the legacy
    names (product_type, max_budget, required_specs) are accepted as aliases
    so older outputs and tests keep working.
    """

    product_type: str | None = Field(
        default=None,
        validation_alias=AliasChoices("product_type", "category"),
        description="What the customer wants to buy (e.g. 'laptop')",
    )
    use_case: str | None = None
    required_specs: list[dict[str, str]] = Field(default_factory=list)
    max_budget: float | None = Field(
        default=None,
        validation_alias=AliasChoices("max_budget", "budget"),
        description="Maximum budget in the request currency",
    )
    currency: str | None = None
    brand: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    min_quality: str | None = None
    hidden_needs: list[str] = Field(default_factory=list)

    def to_structured_request(self) -> dict[str, Any]:
        """Canonical structured request for downstream services (Fix 4.1)."""
        return {
            "category": self.product_type,
            "budget": self.max_budget,
            "currency": self.currency or "USD",
            "use_case": self.use_case,
            "brand": self.brand,
            "attributes": self.attributes,
        }


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
    price_resolved: bool = Field(
        default=False,
        description="True once the price has been resolved from the real catalog record",
    )
    stock_quantity: int = Field(default=0, description="Total sellable inventory across variants")
    max_discount_pct: float = Field(default=0.0, description="Maximum allowed discount for this product (Fix 4.4)")
    discount_pct: float = Field(default=0.0, description="Applied discount percentage (Fix 4.4)")
    discount_available: bool = Field(default=False, description="Discount brings the price into budget (Fix 4.4)")
    final_price: Decimal | None = Field(default=None, description="Price after the applied discount (Fix 4.4)")
    rank: int = Field(default=0, description="Position after deterministic ranking (Fix 4.3)")


class ProductCard(BaseModel):
    product_id: str
    title: str
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: str | None = None
    product_url: str | None = None
    specs: list[ProductSpecValue] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)
    discount_pct: float = Field(default=0.0)
    discount_available: bool = Field(default=False)
    final_price: Decimal | None = None
    in_stock: bool = True


class RecommendationResponse(BaseModel):
    type: str = Field(default="recommendation", description="Structured result type (Fix 4.5)")
    query: str
    store_id: str
    customer_id: str | None = None
    products: list[ProductCard] = Field(default_factory=list)
    rationale: str | None = None
    total_count: int = 0
    latency_ms: float = 0.0
    clarifying_question: str | None = None
    budget: float | None = Field(default=None, description="Customer budget the result was built against (Fix 4.5)")
    discount_available: bool = Field(default=False, description="A discount was needed to fit the budget (Fix 4.5)")
    discount: float = Field(default=0.0, description="Discount percentage applied to the top pick (Fix 4.5)")
    final_price: float | None = Field(default=None, description="Top pick price after discount (Fix 4.5)")


class DiscountInfo(BaseModel):
    product_id: str
    product_title: str
    original_price: Decimal = Decimal("0")
    discount_pct: float = 0.0
    discount_amount: Decimal = Decimal("0")
    price_after_discount: Decimal = Decimal("0")
    product_url: str | None = None
    image_url: str | None = None


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
