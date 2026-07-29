from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.commerce.value_objects.address import Address
from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.commerce.value_objects.money import Money
from app.shared.kernel.aggregate_root import AggregateRoot


class TaxLine(AggregateRoot[str]):
    title: str = Field(..., min_length=1)
    rate: float = Field(..., ge=0)
    price: Money


class Fulfillment(AggregateRoot[str]):
    status: str = Field(default="pending")
    tracking_company: str | None = None
    tracking_number: str | None = None


class LineItem(AggregateRoot[str]):
    variant_id: str | None = None
    product_id: str | None = None
    title: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    price: Money
    tax_lines: list[TaxLine] = Field(default_factory=list)
    discount_allocations: list[dict] = Field(default_factory=list)


class Order(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    org_id: str = Field(..., min_length=1)
    external_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    shipping_address: Address | None = None
    billing_address: Address | None = None
    subtotal_price: Money | None = None
    total_price: Money | None = None
    total_tax: Money | None = None
    total_discount: Money | None = None
    shipping_price: Money | None = None
    financial_status: str = Field(default="pending")
    fulfillment_status: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    cancelled_at: datetime | None = None
    audit: AuditInfo = Field(default_factory=AuditInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = Field(default=None)
