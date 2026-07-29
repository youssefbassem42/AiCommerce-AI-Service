from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.commerce.aggregates.product import Product, ProductOption, Variant
from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.commerce.value_objects.image import Image
from app.domain.commerce.value_objects.money import Money
from app.domain.commerce.value_objects.seo import SEO
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class MoneyModel(BaseModel):
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)

    def to_vo(self) -> Money:
        return Money(amount=Decimal(str(self.amount)), currency=self.currency)

    @classmethod
    def from_vo(cls, vo: Money) -> "MoneyModel":
        return cls(amount=float(vo.amount), currency=vo.currency)


class ImageModel(BaseModel):
    url: str
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    position: Optional[int] = None

    def to_vo(self) -> Image:
        return Image(
            url=self.url,
            alt_text=self.alt_text,
            width=self.width,
            height=self.height,
            position=self.position,
        )

    @classmethod
    def from_vo(cls, vo: Image) -> "ImageModel":
        return cls(
            url=vo.url,
            alt_text=vo.alt_text,
            width=vo.width,
            height=vo.height,
            position=vo.position,
        )


class SEOModel(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url_slug: Optional[str] = None

    def to_vo(self) -> SEO:
        return SEO(title=self.title, description=self.description, url_slug=self.url_slug)

    @classmethod
    def from_vo(cls, vo: SEO) -> "SEOModel":
        return cls(title=vo.title, description=vo.description, url_slug=vo.url_slug)


class AuditInfoModel(BaseModel):
    created_at: Any
    updated_at: Any
    updated_by: Optional[str] = None

    def to_vo(self) -> AuditInfo:
        return AuditInfo(created_at=self.created_at, updated_at=self.updated_at, updated_by=self.updated_by)

    @classmethod
    def from_vo(cls, vo: AuditInfo) -> "AuditInfoModel":
        return cls(created_at=vo.created_at, updated_at=vo.updated_at, updated_by=vo.updated_by)


class VariantModel(BaseModel):
    id: str
    sku: str
    title: str
    price: MoneyModel
    compare_at_price: Optional[MoneyModel] = None
    inventory_quantity: int = 0
    weight: Optional[float] = None
    dimensions: Optional[str] = None

    def to_entity(self) -> Variant:
        return Variant(
            id=self.id,
            sku=self.sku,
            title=self.title,
            price=self.price.to_vo(),
            compare_at_price=self.compare_at_price.to_vo() if self.compare_at_price else None,
            inventory_quantity=self.inventory_quantity,
            weight=self.weight,
            dimensions=self.dimensions,
        )

    @classmethod
    def from_entity(cls, entity: Variant) -> "VariantModel":
        return cls(
            id=entity.id,
            sku=entity.sku,
            title=entity.title,
            price=MoneyModel.from_vo(entity.price),
            compare_at_price=MoneyModel.from_vo(entity.compare_at_price) if entity.compare_at_price else None,
            inventory_quantity=entity.inventory_quantity,
            weight=float(entity.weight) if entity.weight is not None else None,
            dimensions=entity.dimensions,
        )


class ProductOptionModel(BaseModel):
    id: str
    name: str
    values: list[str] = []

    def to_entity(self) -> ProductOption:
        return ProductOption(id=self.id, name=self.name, values=self.values)

    @classmethod
    def from_entity(cls, entity: ProductOption) -> "ProductOptionModel":
        return cls(id=entity.id, name=entity.name, values=entity.values)


class ProductDocument(BaseMongoDocument):
    store_id: str = Field(..., index=True)
    organization_id: str = Field(...)
    external_id: Optional[str] = None
    title: str = Field(...)
    description: Optional[str] = None
    handle: Optional[str] = None
    status: str = Field(default="draft")
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    images: list[ImageModel] = Field(default_factory=list)
    variants: list[VariantModel] = Field(default_factory=list)
    options: list[ProductOptionModel] = Field(default_factory=list)
    seo: SEOModel = Field(default_factory=SEOModel)
    category_id: Optional[str] = None
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)
    metadata: dict[str, Any] = Field(default_factory=dict)
    max_discount_pct: float = Field(default=0.0, description="Maximum allowed discount percentage for this product")
    promo_codes: dict[str, Any] = Field(default_factory=dict, description="Promo codes generated for this product")

    def to_entity(self) -> Product:
        merged_metadata = dict(self.metadata)
        if self.max_discount_pct:
            merged_metadata["max_discount_pct"] = self.max_discount_pct
        if self.promo_codes:
            merged_metadata["promo_codes"] = self.promo_codes
        return Product(
            id=str(self.id),
            store_id=self.store_id,
            organization_id=self.organization_id,
            external_id=self.external_id,
            title=self.title,
            description=self.description,
            handle=self.handle,
            status=self.status,
            product_type=self.product_type,
            vendor=self.vendor,
            tags=self.tags,
            images=[img.to_vo() for img in self.images],
            variants=[v.to_entity() for v in self.variants],
            options=[o.to_entity() for o in self.options],
            seo=self.seo.to_vo(),
            category_id=self.category_id,
            audit=self.audit.to_vo(),
            metadata=merged_metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: Product) -> "ProductDocument":
        metadata = dict(entity.metadata)
        max_discount_pct = float(metadata.pop("max_discount_pct", 0.0))
        promo_codes = metadata.pop("promo_codes", {})
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            external_id=entity.external_id,
            title=entity.title,
            description=entity.description,
            handle=entity.handle,
            status=entity.status,
            product_type=entity.product_type,
            vendor=entity.vendor,
            tags=entity.tags,
            images=[ImageModel.from_vo(img) for img in entity.images],
            variants=[VariantModel.from_entity(v) for v in entity.variants],
            options=[ProductOptionModel.from_entity(o) for o in entity.options],
            seo=SEOModel.from_vo(entity.seo),
            category_id=entity.category_id,
            audit=AuditInfoModel.from_vo(entity.audit),
            metadata=metadata,
            max_discount_pct=max_discount_pct,
            promo_codes=promo_codes,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
