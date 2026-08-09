from datetime import datetime
from decimal import Decimal
from typing import Any, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResultDTO[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class MoneyDTO(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = "USD"


class ImageDTO(BaseModel):
    url: str
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    position: int | None = None


class SEODTO(BaseModel):
    title: str | None = None
    description: str | None = None
    url_slug: str | None = None


class AuditInfoDTO(BaseModel):
    created_at: datetime
    updated_at: datetime
    updated_by: str | None = None


class VariantDTO(BaseModel):
    id: str = ""
    sku: str
    title: str
    price: MoneyDTO
    compare_at_price: MoneyDTO | None = None
    inventory_quantity: int = 0
    weight: Decimal | None = None
    dimensions: str | None = None


class ProductOptionDTO(BaseModel):
    id: str = ""
    name: str
    values: list[str] = []


class ProductCreateDTO(BaseModel):
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
    images: list[ImageDTO] = Field(default_factory=list)
    variants: list[VariantDTO] = Field(default_factory=list)
    options: list[ProductOptionDTO] = Field(default_factory=list)
    seo: SEODTO = Field(default_factory=SEODTO)
    category_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdateDTO(BaseModel):
    title: str | None = None
    description: str | None = None
    handle: str | None = None
    status: str | None = None
    product_type: str | None = None
    vendor: str | None = None
    tags: list[str] | None = None
    images: list[ImageDTO] | None = None
    variants: list[VariantDTO] | None = None
    options: list[ProductOptionDTO] | None = None
    seo: SEODTO | None = None
    category_id: str | None = None
    metadata: dict[str, Any] | None = None


class ProductDTO(BaseModel):
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
    images: list[ImageDTO]
    variants: list[VariantDTO]
    options: list[ProductOptionDTO]
    seo: SEODTO
    category_id: str | None = None
    audit: AuditInfoDTO
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CategoryCreateDTO(BaseModel):
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


class CategoryUpdateDTO(BaseModel):
    name: str | None = None
    description: str | None = None
    handle: str | None = None
    parent_id: str | None = None
    image_url: str | None = None
    sort_order: int | None = None
    product_count: int | None = None


class CategoryDTO(BaseModel):
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
    audit: AuditInfoDTO
    created_at: datetime
    updated_at: datetime


class OrderCreateDTO(BaseModel):
    store_id: str
    organization_id: str
    external_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    line_items: list[Any] = Field(default_factory=list)
    shipping_address: Any | None = None
    billing_address: Any | None = None
    subtotal_price: MoneyDTO | None = None
    total_price: MoneyDTO | None = None
    total_tax: MoneyDTO | None = None
    total_discount: MoneyDTO | None = None
    shipping_price: MoneyDTO | None = None
    financial_status: str = "pending"
    fulfillment_status: str | None = None
    currency: str = "USD"
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderUpdateDTO(BaseModel):
    financial_status: str | None = None
    fulfillment_status: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class LineItemDTO(BaseModel):
    id: str
    variant_id: str | None = None
    product_id: str | None = None
    title: str
    quantity: int
    price: MoneyDTO
    tax_lines: list[Any] = Field(default_factory=list)
    discount_allocations: list[dict] = Field(default_factory=list)


class OrderDTO(BaseModel):
    id: str
    store_id: str
    organization_id: str
    external_id: str | None = None
    customer_id: str | None = None
    customer_email: str | None = None
    line_items: list[LineItemDTO]
    financial_status: str
    fulfillment_status: str | None = None
    currency: str
    notes: str | None = None
    tags: list[str]
    cancelled_at: datetime | None = None
    audit: AuditInfoDTO
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InventoryCreateDTO(BaseModel):
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


class InventoryUpdateDTO(BaseModel):
    quantity: int | None = None
    available: int | None = None
    committed: int | None = None
    incoming: int | None = None
    location_id: str | None = None
    location_name: str | None = None
    low_stock_threshold: int | None = None


class InventoryDTO(BaseModel):
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
    audit: AuditInfoDTO
    created_at: datetime
    updated_at: datetime
