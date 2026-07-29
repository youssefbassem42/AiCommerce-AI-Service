from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecommendationDTO(BaseModel):
    id: str
    conversation_id: str
    customer_id: str
    recommended_product_ids: List[str]
    store_id: str
    accepted: bool
    rationale: str
    created_at: datetime


class BundleSuggestionDTO(BaseModel):
    id: str
    store_id: str
    title: str
    product_ids: List[str]
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
    product_type: Optional[str] = None
    use_case: Optional[str] = None
    required_specs: List[Dict[str, str]] = Field(default_factory=list)
    max_budget: Optional[float] = None
    min_quality: Optional[str] = None
    hidden_needs: List[str] = Field(default_factory=list)


class ScoredProduct(BaseModel):
    product_id: str
    store_id: str
    title: str
    description: Optional[str] = None
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    specs: List[ProductSpecValue] = Field(default_factory=list)
    match_score: float = 0.0
    match_reasons: List[str] = Field(default_factory=list)
    in_stock: bool = True
    score: float = 0.0


class ProductCard(BaseModel):
    product_id: str
    title: str
    price: Decimal = Decimal("0")
    currency: str = "USD"
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    specs: List[ProductSpecValue] = Field(default_factory=list)
    match_reasons: List[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    query: str
    store_id: str
    customer_id: Optional[str] = None
    products: List[ProductCard] = Field(default_factory=list)
    rationale: Optional[str] = None
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
    products: List[DiscountInfo] = Field(default_factory=list)
    total_original: Decimal = Decimal("0")
    total_discount: Decimal = Decimal("0")
    total_after_discount: Decimal = Decimal("0")
    remaining_budget: float = 0.0
    within_budget: bool = True
    promo_code: Optional[str] = None
    rank: int = 0


class BundleProductCard(BaseModel):
    product_id: str
    title: str
    original_price: Decimal = Decimal("0")
    discount_pct: float = 0.0
    discount_amount: Decimal = Decimal("0")
    final_price: Decimal = Decimal("0")
    image_url: Optional[str] = None
    product_url: Optional[str] = None


class BundleResponse(BaseModel):
    query: str
    store_id: str
    customer_id: Optional[str] = None
    budget: float = 0.0
    bundles: List[BundleCandidate] = Field(default_factory=list)
    promo_code: Optional[str] = None
    rationale: Optional[str] = None
    latency_ms: float = 0.0
