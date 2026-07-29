from datetime import UTC, datetime
from typing import Optional

from pydantic import Field

from app.domain.commerce.value_objects.audit import AuditInfo
from app.shared.kernel.aggregate_root import AggregateRoot


class Category(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    org_id: str = Field(..., min_length=1)
    external_id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = Field(default=0)
    product_count: int = Field(default=0, ge=0)
    audit: AuditInfo = Field(default_factory=AuditInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)
