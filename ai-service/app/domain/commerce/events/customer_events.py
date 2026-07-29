from datetime import UTC, datetime

from pydantic import Field

from app.shared.kernel.domain_event import DomainEvent


class CustomerCreated(DomainEvent):
    customer_id: str
    store_id: str
    organization_id: str
    email: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CustomerUpdated(DomainEvent):
    customer_id: str
    store_id: str
    organization_id: str
    changed_fields: list[str]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
