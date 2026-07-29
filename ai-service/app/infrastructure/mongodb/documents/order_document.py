from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.commerce.aggregates.order import Fulfillment, LineItem, Order, TaxLine
from app.domain.commerce.value_objects.address import Address
from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.commerce.value_objects.money import Money
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.product_document import AuditInfoModel, MoneyModel


class AddressModel(BaseModel):
    first_name: str
    last_name: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    zip: str
    country: str
    phone: Optional[str] = None

    def to_vo(self) -> Address:
        return Address(
            first_name=self.first_name,
            last_name=self.last_name,
            line1=self.line1,
            line2=self.line2,
            city=self.city,
            state=self.state,
            zip=self.zip,
            country=self.country,
            phone=self.phone,
        )

    @classmethod
    def from_vo(cls, vo: Address) -> "AddressModel":
        return cls(
            first_name=vo.first_name,
            last_name=vo.last_name,
            line1=vo.line1,
            line2=vo.line2,
            city=vo.city,
            state=vo.state,
            zip=vo.zip,
            country=vo.country,
            phone=vo.phone,
        )


class TaxLineModel(BaseModel):
    id: str
    title: str
    rate: float
    price: MoneyModel

    def to_entity(self) -> TaxLine:
        return TaxLine(id=self.id, title=self.title, rate=self.rate, price=self.price.to_vo())

    @classmethod
    def from_entity(cls, entity: TaxLine) -> "TaxLineModel":
        return cls(id=entity.id, title=entity.title, rate=entity.rate, price=MoneyModel.from_vo(entity.price))


class FulfillmentModel(BaseModel):
    id: str
    status: str = "pending"
    tracking_company: Optional[str] = None
    tracking_number: Optional[str] = None

    def to_entity(self) -> Fulfillment:
        return Fulfillment(
            id=self.id,
            status=self.status,
            tracking_company=self.tracking_company,
            tracking_number=self.tracking_number,
        )

    @classmethod
    def from_entity(cls, entity: Fulfillment) -> "FulfillmentModel":
        return cls(
            id=entity.id,
            status=entity.status,
            tracking_company=entity.tracking_company,
            tracking_number=entity.tracking_number,
        )


class LineItemModel(BaseModel):
    id: str
    variant_id: Optional[str] = None
    product_id: Optional[str] = None
    title: str
    quantity: int
    price: MoneyModel
    tax_lines: list[TaxLineModel] = Field(default_factory=list)
    discount_allocations: list[dict] = Field(default_factory=list)

    def to_entity(self) -> LineItem:
        return LineItem(
            id=self.id,
            variant_id=self.variant_id,
            product_id=self.product_id,
            title=self.title,
            quantity=self.quantity,
            price=self.price.to_vo(),
            tax_lines=[t.to_entity() for t in self.tax_lines],
            discount_allocations=self.discount_allocations,
        )

    @classmethod
    def from_entity(cls, entity: LineItem) -> "LineItemModel":
        return cls(
            id=entity.id,
            variant_id=entity.variant_id,
            product_id=entity.product_id,
            title=entity.title,
            quantity=entity.quantity,
            price=MoneyModel.from_vo(entity.price),
            tax_lines=[TaxLineModel.from_entity(t) for t in entity.tax_lines],
            discount_allocations=entity.discount_allocations,
        )


class OrderDocument(BaseMongoDocument):
    store_id: str = Field(..., index=True)
    org_id: str = Field(...)
    external_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    line_items: list[LineItemModel] = Field(default_factory=list)
    shipping_address: Optional[AddressModel] = None
    billing_address: Optional[AddressModel] = None
    subtotal_price: Optional[MoneyModel] = None
    total_price: Optional[MoneyModel] = None
    total_tax: Optional[MoneyModel] = None
    total_discount: Optional[MoneyModel] = None
    shipping_price: Optional[MoneyModel] = None
    financial_status: str = "pending"
    fulfillment_status: Optional[str] = None
    currency: str = "USD"
    notes: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    cancelled_at: Optional[datetime] = None
    audit: AuditInfoModel = Field(default_factory=AuditInfoModel)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> Order:
        return Order(
            id=str(self.id),
            store_id=self.store_id,
            org_id=self.org_id,
            external_id=self.external_id,
            customer_id=self.customer_id,
            customer_email=self.customer_email,
            line_items=[li.to_entity() for li in self.line_items],
            shipping_address=self.shipping_address.to_vo() if self.shipping_address else None,
            billing_address=self.billing_address.to_vo() if self.billing_address else None,
            subtotal_price=self.subtotal_price.to_vo() if self.subtotal_price else None,
            total_price=self.total_price.to_vo() if self.total_price else None,
            total_tax=self.total_tax.to_vo() if self.total_tax else None,
            total_discount=self.total_discount.to_vo() if self.total_discount else None,
            shipping_price=self.shipping_price.to_vo() if self.shipping_price else None,
            financial_status=self.financial_status,
            fulfillment_status=self.fulfillment_status,
            currency=self.currency,
            notes=self.notes,
            tags=self.tags,
            cancelled_at=self.cancelled_at,
            audit=self.audit.to_vo(),
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: Order) -> "OrderDocument":
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            customer_id=entity.customer_id,
            customer_email=entity.customer_email,
            line_items=[LineItemModel.from_entity(li) for li in entity.line_items],
            shipping_address=AddressModel.from_vo(entity.shipping_address) if entity.shipping_address else None,
            billing_address=AddressModel.from_vo(entity.billing_address) if entity.billing_address else None,
            subtotal_price=MoneyModel.from_vo(entity.subtotal_price) if entity.subtotal_price else None,
            total_price=MoneyModel.from_vo(entity.total_price) if entity.total_price else None,
            total_tax=MoneyModel.from_vo(entity.total_tax) if entity.total_tax else None,
            total_discount=MoneyModel.from_vo(entity.total_discount) if entity.total_discount else None,
            shipping_price=MoneyModel.from_vo(entity.shipping_price) if entity.shipping_price else None,
            financial_status=entity.financial_status,
            fulfillment_status=entity.fulfillment_status,
            currency=entity.currency,
            notes=entity.notes,
            tags=entity.tags,
            cancelled_at=entity.cancelled_at,
            audit=AuditInfoModel.from_vo(entity.audit),
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
