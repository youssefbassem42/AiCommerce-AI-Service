from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrackCopyEventRequest(BaseModel):
    store_id: str = Field(..., min_length=1)
    promo_code: str = Field(..., min_length=1)
    product_ids: List[str] = Field(..., min_length=1)
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
    product_ids: List[str]
    discount_pct: float
    total_original: float
    total_discount: float
    promo_code: str
    copy_count: int
    is_top: bool
    promoted_at: Optional[str] = None
    first_copied_at: Optional[str] = None
    last_copied_at: Optional[str] = None


class PromoteBundleRequest(BaseModel):
    bundle_key: str = Field(..., min_length=1)


class DemoteBundleRequest(BaseModel):
    bundle_key: str = Field(..., min_length=1)


class TrackingConfigResponse(BaseModel):
    threshold: int
    enabled: bool


class TrackingConfigUpdateRequest(BaseModel):
    threshold: Optional[int] = Field(None, ge=1, le=100)
    enabled: Optional[bool] = None


class TrackingConfigUpdateResponse(BaseModel):
    threshold: int
    enabled: bool
