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
