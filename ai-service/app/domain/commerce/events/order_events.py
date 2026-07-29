from datetime import datetime, UTC
from typing import List
from pydantic import Field

from app.shared.kernel.domain_event import DomainEvent


class OrderPlaced(DomainEvent):
    order_id: str
    store_id: str
    organization_id: str
    customer_id: str
    total: float
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderUpdated(DomainEvent):
    order_id: str
    store_id: str
    organization_id: str
    changed_fields: List[str]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderCancelled(DomainEvent):
    order_id: str
    store_id: str
    organization_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
