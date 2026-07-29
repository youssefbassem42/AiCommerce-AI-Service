from datetime import datetime, UTC
from typing import List, Optional
from pydantic import Field

from app.shared.kernel.domain_event import DomainEvent


class CustomerCreated(DomainEvent):
    customer_id: str
    store_id: str
    organization_id: str
    email: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CustomerUpdated(DomainEvent):
    customer_id: str
    store_id: str
    organization_id: str
    changed_fields: List[str]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
