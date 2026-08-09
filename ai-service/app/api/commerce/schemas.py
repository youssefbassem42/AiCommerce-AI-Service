from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class MoneySchema(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = "USD"


class ImageSchema(BaseModel):
    url: str
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    position: int | None = None


class SEOSchema(BaseModel):
    title: str | None = None
    description: str | None = None
    url_slug: str | None = None


class AuditInfoSchema(BaseModel):
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None


class VariantCreateSchema(BaseModel):
    sku: str
    title: str
    price: MoneySchema
    compare_at_price: MoneySchema | None = None
    inventory_quantity: int = 0
    weight: Decimal | None = None
    dimensions: str | None = None


class VariantResponseSchema(BaseModel):
    id: str
    sku: str
    title: str
    price: MoneySchema
    compare_at_price: MoneySchema | None = None
    inventory_quantity: int
    weight: Decimal | None = None
    dimensions: str | None = None


class ProductOptionSchema(BaseModel):
    name: str
    values: list[str] = Field(default_factory=list)


class ProductOptionResponseSchema(BaseModel):
    id: str
    name: str
    values: list[str]


class ProductCreateSchema(BaseModel):
    store_id: str
    organization_id: str
    external_id: str | None = None
    title: str
    description: str | None = None
    handle: str | None = None
    status: str = "draft"
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] = Field(default_factory=list)
    images: list[ImageSchema] = Field(default_factory=list)
    variants: list[VariantCreateSchema] = Field(default_factory=list)
    options: list[ProductOptionSchema] = Field(default_factory=list)
    seo: SEOSchema = Field(default_factory=SEOSchema)
    category_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdateSchema(BaseModel):
    title: str | None = None
    description: str | None = None
    handle: str | None = None
    status: str | None = None
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] | None = None
    images: list[ImageSchema] | None = None
    variants: list[VariantCreateSchema] | None = None
    options: list[ProductOptionSchema] | None = None
    seo: SEOSchema | None = None
    category_id: str | None = None
    metadata: dict[str, Any] | None = None


class ProductResponseSchema(BaseModel):
    id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    title: str
    description: str | None = None
    handle: str | None = None
    status: str
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str]
    images: list[ImageSchema]
    variants: list[VariantResponseSchema]
    options: list[ProductOptionResponseSchema]
    seo: SEOSchema
    category_id: str | None = None
    audit: AuditInfoSchema
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CategoryCreateSchema(BaseModel):
    store_id: str
    organization_id: str
    external_id: str | None = None
    name: str
    description: str | None = None
    handle: str | None = None
    parent_id: str | None = None
    image_url: str | None = None
    sort_order: int = 0
    product_count: int = 0


class CategoryUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None
    handle: str | None = None
    parent_id: str | None = None
    image_url: str | None = None
    sort_order: int | None = None
    product_count: int | None = None


class CategoryResponseSchema(BaseModel):
    id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    name: str
    description: str | None = None
    handle: str | None = None
    parent_id: str | None = None
    image_url: str | None = None
    sort_order: int
    product_count: int
    audit: AuditInfoSchema
    created_at: datetime
    updated_at: datetime


class OrderCreateSchema(BaseModel):
    store_id: str
    organization_id: str
    external_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    financial_status: str = "pending"
    fulfillment_status: str | None = None
    currency: str = "USD"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderUpdateStatusSchema(BaseModel):
    financial_status: str | None = None
    fulfillment_status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class OrderResponseSchema(BaseModel):
    id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    line_items: list[Any] = Field(default_factory=list)
    financial_status: str
    fulfillment_status: str | None = None
    currency: str
    notes: str | None = None
    tags: list[str]
    cancelled_at: datetime | None = None
    audit: AuditInfoSchema
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InventoryCreateSchema(BaseModel):
    product_id: str
    variant_id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    quantity: int = 0
    available: int = 0
    committed: int = 0
    incoming: int = 0
    location_id: str | None = None
    location_name: str | None = None
    low_stock_threshold: int | None = None


class InventoryUpdateSchema(BaseModel):
    quantity: int | None = None
    available: int | None = None
    committed: int | None = None
    incoming: int | None = None
    location_id: str | None = None
    location_name: str | None = None
    low_stock_threshold: int | None = None


class InventoryResponseSchema(BaseModel):
    id: str
    product_id: str
    variant_id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    quantity: int
    available: int
    committed: int
    incoming: int
    location_id: str | None = None
    location_name: str | None = None
    low_stock_threshold: int | None = None
    audit: AuditInfoSchema
    created_at: datetime
    updated_at: datetime


class PaginatedResponseSchema(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class DeleteResponseSchema(BaseModel):
    success: bool
