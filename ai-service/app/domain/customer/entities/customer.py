from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.commerce.value_objects.audit import AuditInfo
from app.shared.kernel.aggregate_root import AggregateRoot


class Customer(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    external_id: str | None = None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    accepts_marketing: bool = False
    audit: AuditInfo = Field(default_factory=AuditInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = Field(default=None)
