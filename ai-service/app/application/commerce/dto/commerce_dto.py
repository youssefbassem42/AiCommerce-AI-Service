from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResultDTO(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class MoneyDTO(BaseModel):
    amount: Decimal = Field(..., ge=0)
    currency: str = "USD"


class ImageDTO(BaseModel):
    url: str
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None


class SEODTO(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url_slug: Optional[str] = None


class AuditInfoDTO(BaseModel):
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None


class VariantDTO(BaseModel):
    id: str = ""
    sku: str
    title: str
    price: MoneyDTO
    compare_at_price: Optional[MoneyDTO] = None
    inventory_quantity: int = 0
    weight: Optional[Decimal] = None
    dimensions: Optional[str] = None


class ProductOptionDTO(BaseModel):
    id: str = ""
    name: str
    values: list[str] = []


class ProductCreateDTO(BaseModel):
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
    images: list[ImageDTO] = Field(default_factory=list)
    variants: list[VariantDTO] = Field(default_factory=list)
    options: list[ProductOptionDTO] = Field(default_factory=list)
    seo: SEODTO = Field(default_factory=SEODTO)
    category_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductUpdateDTO(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    handle: Optional[str] = None
    status: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[list[str]] = None
    images: Optional[list[ImageDTO]] = None
    variants: Optional[list[VariantDTO]] = None
    options: Optional[list[ProductOptionDTO]] = None
    seo: Optional[SEODTO] = None
    category_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class ProductDTO(BaseModel):
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
    images: list[ImageDTO]
    variants: list[VariantDTO]
    options: list[ProductOptionDTO]
    seo: SEODTO
    category_id: Optional[str] = None
    audit: AuditInfoDTO
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CategoryCreateDTO(BaseModel):
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


class CategoryUpdateDTO(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    handle: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    sort_order: Optional[int] = None
    product_count: Optional[int] = None


class CategoryDTO(BaseModel):
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
    audit: AuditInfoDTO
    created_at: datetime
    updated_at: datetime


class OrderCreateDTO(BaseModel):
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    line_items: list[Any] = Field(default_factory=list)
    shipping_address: Optional[Any] = None
    billing_address: Optional[Any] = None
    subtotal_price: Optional[MoneyDTO] = None
    total_price: Optional[MoneyDTO] = None
    total_tax: Optional[MoneyDTO] = None
    total_discount: Optional[MoneyDTO] = None
    shipping_price: Optional[MoneyDTO] = None
    financial_status: str = "pending"
    fulfillment_status: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrderUpdateDTO(BaseModel):
    financial_status: Optional[str] = None
    fulfillment_status: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None


class LineItemDTO(BaseModel):
    id: str
    variant_id: Optional[str] = None
    product_id: Optional[str] = None
    title: str
    quantity: int
    price: MoneyDTO
    tax_lines: list[Any] = Field(default_factory=list)
    discount_allocations: list[dict] = Field(default_factory=list)


class OrderDTO(BaseModel):
    id: str
    store_id: str
    org_id: str
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    line_items: list[LineItemDTO]
    financial_status: str
    fulfillment_status: Optional[str] = None
    currency: str
    notes: Optional[str] = None
    tags: list[str]
    cancelled_at: Optional[datetime] = None
    audit: AuditInfoDTO
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class InventoryCreateDTO(BaseModel):
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


class InventoryUpdateDTO(BaseModel):
    quantity: Optional[int] = None
    available: Optional[int] = None
    committed: Optional[int] = None
    incoming: Optional[int] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    low_stock_threshold: Optional[int] = None


class InventoryDTO(BaseModel):
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
    audit: AuditInfoDTO
    created_at: datetime
    updated_at: datetime
