from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.commerce.value_objects.image import Image
from app.domain.commerce.value_objects.money import Money
from app.domain.commerce.value_objects.seo import SEO
from app.shared.kernel.aggregate_root import AggregateRoot


class ProductOption(AggregateRoot[str]):
    name: str = Field(..., min_length=1)
    values: list[str] = Field(default_factory=list)


class Variant(AggregateRoot[str]):
    sku: str | None = None
    title: str = Field(..., min_length=1)
    price: Money
    compare_at_price: Money | None = None
    inventory_quantity: int = Field(default=0)
    weight: Decimal | None = Field(default=None, ge=0)
    dimensions: str | None = None


class Product(AggregateRoot[str]):
    store_id: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    external_id: str | None = None
    title: str = Field(..., min_length=1)
    description: str | None = None
    handle: str | None = None
    status: str = Field(default="draft")
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    images: list[Image] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    options: list[ProductOption] = Field(default_factory=list)
    seo: SEO = Field(default_factory=SEO)
    category_id: str | None = None
    audit: AuditInfo = Field(default_factory=AuditInfo)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: datetime | None = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"active", "draft", "archived"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}, got '{v}'")
        return v

    def add_variant(self, variant: Variant) -> None:
        if any(v.sku == variant.sku for v in self.variants):
            raise ValueError(f"Variant with SKU '{variant.sku}' already exists")
        self.variants.append(variant)

    def remove_variant(self, variant_id: str) -> None:
        self.variants = [v for v in self.variants if v.id != variant_id]

    def update_price(self, variant_id: str, new_price: Money) -> None:
        for v in self.variants:
            if v.id == variant_id:
                v.price = new_price
                return
        raise ValueError(f"Variant with id '{variant_id}' not found")

    def update_inventory(self, variant_id: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("Inventory quantity cannot be negative")
        for v in self.variants:
            if v.id == variant_id:
                v.inventory_quantity = quantity
                return
        raise ValueError(f"Variant with id '{variant_id}' not found")

    def activate(self) -> None:
        self.status = "active"

    def archive(self) -> None:
        self.status = "archived"
