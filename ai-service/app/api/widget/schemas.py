from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.rag.schemas import (
    ChunkReferenceSchema,
    CitationSchema,
    UsageSchema,
)


class WidgetConfigurationSchema(BaseModel):
    chat: bool = False
    recommendations: bool = False


class WidgetBootstrapResponseSchema(BaseModel):
    access_token: str
    expires_in: int
    widget_id: str
    configuration: WidgetConfigurationSchema


class WidgetChatRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    customer_id: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=64, le=8192)
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    use_hybrid: bool = False
    use_mmr: bool = False
    rerank: bool = False
    language: str | None = None
    knowledge_scope: str | None = None
    message_id: str | None = None


class WidgetChatResponseSchema(BaseModel):
    response: str
    citations: list[CitationSchema] = Field(default_factory=list)
    chunk_references: list[ChunkReferenceSchema] = Field(default_factory=list)
    confidence_score: float = 0.0
    latency_ms: float = 0.0
    model: str
    provider: str
    usage: UsageSchema = Field(default_factory=UsageSchema)
    business_summary_version: int | None = None
    conversation_id: str | None = None
    type: Literal["text", "products", "product_detail", "bundle", "ticket_created", "escalation", "error"] = "text"
    products: list[dict] = Field(default_factory=list)
    product: dict | None = None
    bundle: dict | None = None
    message_id: str | None = None
    request_id: str | None = None
    reference: str | None = None


class WidgetRecommendationRequestSchema(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    customer_id: str | None = None
    conversation_id: str | None = None


class WidgetRecommendationResponseSchema(BaseModel):
    query: str
    products: list[dict] = Field(default_factory=list)
    rationale: str | None = None
    total_count: int = 0
    latency_ms: float = 0.0
    customer_id: str | None = None
    type: str = "recommendation"
    budget: float | None = None
    discount_available: bool = False
    discount: float = 0.0
    final_price: float | None = None


class WidgetBundleEventRequestSchema(BaseModel):
    """Bundle funnel analytics event from the widget (Fix 5.6)."""

    event: Literal["bundle_clicked", "promo_copied", "promo_applied"]
    bundle_key: str | None = None
    product_ids: list[str] = Field(default_factory=list)
    promo_code: str | None = None
    discount_pct: float | None = None
    conversation_id: str | None = None
    customer_id: str | None = None


class WidgetBundleEventResponseSchema(BaseModel):
    event: str
    recorded: bool


class WidgetInstallationCreateRequestSchema(BaseModel):
    environment: str = Field(default="live", pattern="^(live|test)$")
    allowed_origins: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)


class WidgetInstallationCreateResponseSchema(BaseModel):
    widget_key: str
    widget_id: str
    store_id: str
    organization_id: str
    environment: str
    status: str
    allowed_origins: list[str]
    scopes: list[str]
    install_snippet: str


class WidgetInstallationListResponseSchema(BaseModel):
    id: str
    widget_id: str
    environment: str
    status: str
    allowed_origins: list[str]
    scopes: list[str]
    last_used_at: datetime | None = None
    created_at: datetime
