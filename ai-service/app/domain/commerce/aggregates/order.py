from datetime import UTC, datetime
from typing import Any, Optional

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
    tracking_company: Optional[str] = None
    tracking_number: Optional[str] = None


class LineItem(AggregateRoot[str]):
    variant_id: Optional[str] = None
    product_id: Optional[str] = None
    title: str = Field(..., min_length=1)
    quantity: int = Field(..., ge=1)
    price: Money
    tax_lines: list[TaxLine] = Field(default_factory=list)
    discount_allocations: list[dict] = Field(default_factory=list)


class Order(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    org_id: str = Field(..., min_length=1)
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    shipping_address: Optional[Address] = None
    billing_address: Optional[Address] = None
    subtotal_price: Optional[Money] = None
    total_price: Optional[Money] = None
    total_tax: Optional[Money] = None
    total_discount: Optional[Money] = None
    shipping_price: Optional[Money] = None
    financial_status: str = Field(default="pending")
    fulfillment_status: Optional[str] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    cancelled_at: Optional[datetime] = None
    audit: AuditInfo = Field(default_factory=AuditInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)
