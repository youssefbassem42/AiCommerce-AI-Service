from pydantic import BaseModel, Field


class TrackCopyEventRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    promo_code: str = Field(..., min_length=1)
    product_ids: list[str] = Field(..., min_length=1)
    discount_pct: float = Field(..., ge=0, le=100)
    total_discount: float = Field(..., ge=0)
    total_original: float = Field(..., ge=0)


class TrackCopyEventResponse(BaseModel):
    bundle_key: str
    copy_count: int
    is_top: bool
    threshold: int


class TrackedBundleResponse(BaseModel):
    id: str
    store_id: str
    bundle_key: str
    product_ids: list[str]
    discount_pct: float
    total_original: float
    total_discount: float
    promo_code: str
    copy_count: int
    is_top: bool
    promoted_at: str | None = None
    first_copied_at: str | None = None
    last_copied_at: str | None = None


class PromoteBundleRequest(BaseModel):
    bundle_key: str = Field(..., min_length=1)


class DemoteBundleRequest(BaseModel):
    bundle_key: str = Field(..., min_length=1)


class TrackingConfigResponse(BaseModel):
    threshold: int
    enabled: bool


class TrackingConfigUpdateRequest(BaseModel):
    threshold: int | None = Field(None, ge=1, le=100)
    enabled: bool | None = None


class TrackingConfigUpdateResponse(BaseModel):
    threshold: int
    enabled: bool


# ── Prompt Schemas ──────────────────────────────────────────────


class PromptCreateRequest(BaseModel):
    key: str = Field(..., min_length=1, pattern=r"^[a-zA-Z0-9._-]+$")
    type: str = Field(default="system", pattern=r"^(system|user|template)$")
    content: str = Field(..., min_length=1)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)


class PromptUpdateRequest(BaseModel):
    content: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    type: str | None = Field(None, pattern=r"^(system|user|template)$")
    variables: list[str] | None = None
    is_active: bool | None = None


class PromptResponse(BaseModel):
    id: str
    key: str
    type: str
    content: str
    description: str
    tags: list[str]
    version: int
    is_active: bool
    variables: list[str]
    created_at: str
    updated_at: str


class PromptListResponse(BaseModel):
    items: list[PromptResponse]
    total: int
    page: int
    page_size: int


# ── Admin Analytics Schemas ──────────────────────────────────────


class SentimentOverviewResponse(BaseModel):
    total: int
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float
