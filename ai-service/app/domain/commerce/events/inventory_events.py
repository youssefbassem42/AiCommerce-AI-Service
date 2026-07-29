from datetime import datetime, UTC
from pydantic import Field

from app.shared.kernel.domain_event import DomainEvent


class InventoryChanged(DomainEvent):
    product_id: str
    variant_id: str
    store_id: str
    organization_id: str
    old_quantity: int
    new_quantity: int
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StockAlert(DomainEvent):
    product_id: str
    variant_id: str
    store_id: str
    organization_id: str
    current_quantity: int
    threshold: int
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
