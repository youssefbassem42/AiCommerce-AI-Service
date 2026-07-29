from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.commerce.value_objects.audit import AuditInfo
from app.shared.kernel.aggregate_root import AggregateRoot


class Customer(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    external_id: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    accepts_marketing: bool = False
    audit: AuditInfo = Field(default_factory=AuditInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)
