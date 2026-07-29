from datetime import datetime, UTC
from typing import List, Optional
from pydantic import Field

from app.shared.kernel.domain_event import DomainEvent


class ProductCreated(DomainEvent):
    product_id: str
    store_id: str
    organization_id: str
    external_id: Optional[str] = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductUpdated(DomainEvent):
    product_id: str
    store_id: str
    organization_id: str
    changed_fields: List[str]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductDeleted(DomainEvent):
    product_id: str
    store_id: str
    organization_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductSynced(DomainEvent):
    product_id: str
    store_id: str
    organization_id: str
    platform: str
    sync_session_id: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
