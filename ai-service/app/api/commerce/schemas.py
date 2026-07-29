from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class MoneySchema(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = "USD"


class ImageSchema(BaseModel):
    url: str
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None


class SEOSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url_slug: Optional[str] = None


class AuditInfoSchema(BaseModel):
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None


class VariantCreateSchema(BaseModel):
    sku: str
    title: str
    price: MoneySchema
    compare_at_price: Optional[MoneySchema] = None
    inventory_quantity: int = 0
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None


class VariantResponseSchema(BaseModel):
    id: str
    sku: str
    title: str
    price: MoneySchema
    compare_at_price: Optional[MoneySchema] = None
    inventory_quantity: int
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None


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
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    handle: Optional[str] = None
    status: str = "draft"
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    images: list[ImageSchema] = Field(default_factory=list)
    variants: list[VariantCreateSchema] = Field(default_factory=list)
    options: list[ProductOptionSchema] = Field(default_factory=list)
    seo: SEOSchema = Field(default_factory=SEOSchema)
    category_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    handle: Optional[str] = None
    status: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[ImageSchema]] = None
    variants: Optional[list[VariantCreateSchema]] = None
    options: Optional[list[ProductOptionSchema]] = None
    seo: Optional[SEOSchema] = None
    category_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ProductResponseSchema(BaseModel):
    id: str
    store_id: str
    organization_id: str
    external_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    handle: Optional[str] = None
    status: str
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: list[str]
    images: list[ImageSchema]
    variants: list[VariantResponseSchema]
    options: list[ProductOptionResponseSchema]
    seo: SEOSchema
    category_id: Optional[str] = None
    audit: AuditInfoSchema
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CategoryCreateSchema(BaseModel):
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int = 0
    product_count: int = 0


class CategoryUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None
    product_count: Optional[int] = None


class CategoryResponseSchema(BaseModel):
    id: str
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: int
    product_count: int
    audit: AuditInfoSchema
    created_at: datetime
    updated_at: datetime


class OrderCreateSchema(BaseModel):
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    financial_status: str = "pending"
    fulfillment_status: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderUpdateStatusSchema(BaseModel):
    financial_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class OrderResponseSchema(BaseModel):
    id: str
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    line_items: list[Any] = Field(default_factory=list)
    financial_status: str
    fulfillment_status: Optional[str] = None
    currency: str
    notes: Optional[str] = None
    tags: list[str]
    cancelled_at: Optional[datetime] = None
    audit: AuditInfoSchema
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InventoryCreateSchema(BaseModel):
    product_id: str
    variant_id: str
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    quantity: int = 0
    available: int = 0
    committed: int = 0
    incoming: int = 0
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = None


class InventoryUpdateSchema(BaseModel):
    quantity: Optional[int] = None
    available: Optional[int] = None
    committed: Optional[int] = None
    incoming: Optional[int] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = None


class InventoryResponseSchema(BaseModel):
    id: str
    product_id: str
    variant_id: str
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    quantity: int
    available: int
    committed: int
    incoming: int
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = None
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
