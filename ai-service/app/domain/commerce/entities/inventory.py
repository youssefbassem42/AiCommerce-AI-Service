from datetime import UTC, datetime
from typing import Optional

from pydantic import Field

from app.domain.commerce.value_objects.audit import AuditInfo
from app.shared.kernel.entity import Entity


class Inventory(Entity[str]):
    product_id: str = Field(..., min_length=1)
    variant_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    org_id: str = Field(..., min_length=1)
    external_id: Optional[str] = None
    quantity: int = Field(default=0)
    available: int = Field(default=0, ge=0)
    committed: int = Field(default=0, ge=0)
    incoming: int = Field(default=0, ge=0)
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    audit: AuditInfo = Field(default_factory=AuditInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)
