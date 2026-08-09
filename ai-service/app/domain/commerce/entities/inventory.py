from datetime import UTC, datetime

from pydantic import Field

from app.domain.commerce.value_objects.audit import AuditInfo
from app.shared.kernel.entity import Entity


class Inventory(Entity[str]):
    product_id: str = Field(..., min_length=1)
    variant_id: str = Field(..., min_length=1)
    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    external_id: str | None = None
    quantity: int = Field(default=0)
    available: int = Field(default=0, ge=0)
    committed: int = Field(default=0, ge=0)
    incoming: int = Field(default=0, ge=0)
    location_id: str | None = None
    location_name: str | None = None
    low_stock_threshold: int | None = Field(default=None, ge=0)
    audit: AuditInfo = Field(default_factory=AuditInfo)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = Field(default=None)
