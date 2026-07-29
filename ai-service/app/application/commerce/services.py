from __future__ import annotations

from datetime import UTC, datetime

from bson import ObjectId

from app.application.commerce.dto.commerce_dto import (
    AuditInfoDTO,
    CategoryCreateDTO,
    CategoryDTO,
    CategoryUpdateDTO,
    ImageDTO,
    InventoryCreateDTO,
    InventoryDTO,
    InventoryUpdateDTO,
    LineItemDTO,
    MoneyDTO,
    OrderCreateDTO,
    OrderDTO,
    OrderUpdateDTO,
    PaginatedResultDTO,
    ProductCreateDTO,
    ProductDTO,
    ProductOptionDTO,
    ProductUpdateDTO,
    SEODTO,
    VariantDTO,
)
from app.domain.commerce.aggregates.category import Category
from app.domain.commerce.aggregates.order import LineItem, Order
from app.domain.commerce.aggregates.product import Product, ProductOption, Variant
from app.domain.commerce.entities.inventory import Inventory
from app.domain.commerce.exceptions import (
    CategoryNotFoundException,
    InventoryNotFoundException,
    OrderNotFoundException,
    ProductNotFoundException,
)
from app.domain.commerce.repositories import (
    CategoryRepository,
    InventoryRepository,
    OrderRepository,
    ProductRepository,
)
from app.domain.commerce.value_objects.audit import AuditInfo
from app.domain.commerce.value_objects.image import Image
from app.domain.commerce.value_objects.money import Money
from app.domain.commerce.value_objects.seo import SEO


def _new_id() -> str:
    return str(ObjectId())


class ProductService:

    def __init__(self, repository: ProductRepository):
        self.repository = repository

    async def create(self, data: ProductCreateDTO) -> ProductDTO:
        entity = Product(
            id=_new_id(),
            store_id=data.store_id,
            organization_id=data.organization_id,
            external_id=data.external_id,
            title=data.title,
            description=data.description,
            handle=data.handle,
            status=data.status,
            product_type=data.product_type,
            vendor=data.vendor,
            tags=data.tags,
            images=[Image(**img.model_dump()) for img in data.images],
            variants=[Variant(id=_new_id(), **v.model_dump(exclude={"id"})) for v in data.variants],
            options=[ProductOption(id=_new_id(), **o.model_dump(exclude={"id"})) for o in data.options],
            seo=SEO(**data.seo.model_dump()) if data.seo else SEO(),
            category_id=data.category_id,
            metadata=data.metadata,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_id(self, product_id: str) -> ProductDTO:
        entity = await self.repository.find_by_id(product_id)
        if entity is None:
            raise ProductNotFoundException(f"Product '{product_id}' was not found.")
        return self._to_dto(entity)

    async def list(
        self, page: int = 1, page_size: int = 20, store_id: str | None = None, status: str | None = None
    ) -> PaginatedResultDTO[ProductDTO]:
        filters: dict = {}
        if store_id:
            filters["store_id"] = store_id
        if status:
            filters["status"] = status
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[ProductDTO](
            items=[self._to_dto(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, product_id: str, data: ProductUpdateDTO) -> ProductDTO:
        entity = await self.repository.find_by_id(product_id)
        if entity is None:
            raise ProductNotFoundException(f"Product '{product_id}' was not found.")
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                if field == "images":
                    setattr(entity, field, [Image(**img) for img in value])
                elif field == "variants":
                    existing_ids = {v.id for v in entity.variants}
                    new_variants = []
                    for v in value:
                        v_id = v.get("id")
                        if v_id and v_id in existing_ids:
                            new_variants.append(Variant(id=v_id, **{k: vv for k, vv in v.items() if k != "id"}))
                        else:
                            new_variants.append(Variant(id=_new_id(), **{k: vv for k, vv in v.items() if k != "id"}))
                    setattr(entity, field, new_variants)
                elif field == "options":
                    existing_ids = {o.id for o in entity.options}
                    new_options = []
                    for o in value:
                        o_id = o.get("id")
                        if o_id and o_id in existing_ids:
                            new_options.append(ProductOption(id=o_id, **{k: vv for k, vv in o.items() if k != "id"}))
                        else:
                            new_options.append(ProductOption(id=_new_id(), **{k: vv for k, vv in o.items() if k != "id"}))
                    setattr(entity, field, new_options)
                elif field == "seo" and value is not None:
                    setattr(entity, field, SEO(**value))
                else:
                    setattr(entity, field, value)
        entity.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def delete(self, product_id: str) -> bool:
        deleted = await self.repository.delete(product_id)
        if not deleted:
            raise ProductNotFoundException(f"Product '{product_id}' was not found.")
        return deleted

    @staticmethod
    def _to_dto(entity: Product) -> ProductDTO:
        return ProductDTO(
            id=entity.id,
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
            images=[ImageDTO(**img.model_dump()) for img in entity.images],
            variants=[VariantDTO(id=v.id, sku=v.sku, title=v.title, price=MoneyDTO(**v.price.model_dump()), compare_at_price=MoneyDTO(**v.compare_at_price.model_dump()) if v.compare_at_price else None, inventory_quantity=v.inventory_quantity, weight=v.weight, dimensions=v.dimensions) for v in entity.variants],
            options=[ProductOptionDTO(id=o.id, name=o.name, values=o.values) for o in entity.options],
            seo=SEODTO(**entity.seo.model_dump()),
            category_id=entity.category_id,
            audit=AuditInfoDTO(**entity.audit.model_dump()),
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class CategoryService:

    def __init__(self, repository: CategoryRepository):
        self.repository = repository

    async def create(self, data: CategoryCreateDTO) -> CategoryDTO:
        entity = Category(
            id=_new_id(),
            store_id=data.store_id,
            org_id=data.org_id,
            external_id=data.external_id,
            name=data.name,
            description=data.description,
            handle=data.handle,
            parent_id=data.parent_id,
            image_url=data.image_url,
            sort_order=data.sort_order,
            product_count=data.product_count,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_id(self, category_id: str) -> CategoryDTO:
        entity = await self.repository.find_by_id(category_id)
        if entity is None:
            raise CategoryNotFoundException(f"Category '{category_id}' was not found.")
        return self._to_dto(entity)

    async def list(
        self, page: int = 1, page_size: int = 20, store_id: str | None = None
    ) -> PaginatedResultDTO[CategoryDTO]:
        filters: dict = {}
        if store_id:
            filters["store_id"] = store_id
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[CategoryDTO](
            items=[self._to_dto(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, category_id: str, data: CategoryUpdateDTO) -> CategoryDTO:
        entity = await self.repository.find_by_id(category_id)
        if entity is None:
            raise CategoryNotFoundException(f"Category '{category_id}' was not found.")
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                setattr(entity, field, value)
        entity.audit.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def delete(self, category_id: str) -> bool:
        deleted = await self.repository.delete(category_id)
        if not deleted:
            raise CategoryNotFoundException(f"Category '{category_id}' was not found.")
        return deleted

    async def get_children(self, parent_id: str) -> list[CategoryDTO]:
        items = await self.repository.find_children(parent_id)
        return [self._to_dto(item) for item in items]

    async def get_root_categories(self, store_id: str) -> list[CategoryDTO]:
        items = await self.repository.find_root(store_id)
        return [self._to_dto(item) for item in items]

    @staticmethod
    def _to_dto(entity: Category) -> CategoryDTO:
        return CategoryDTO(
            id=entity.id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            name=entity.name,
            description=entity.description,
            handle=entity.handle,
            parent_id=entity.parent_id,
            image_url=entity.image_url,
            sort_order=entity.sort_order,
            product_count=entity.product_count,
            audit=AuditInfoDTO(**entity.audit.model_dump()),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class OrderService:

    def __init__(self, repository: OrderRepository):
        self.repository = repository

    async def create(self, data: OrderCreateDTO) -> OrderDTO:
        entity = Order(
            id=_new_id(),
            store_id=data.store_id,
            org_id=data.org_id,
            external_id=data.external_id,
            customer_id=data.customer_id,
            customer_email=data.customer_email,
            line_items=[
                LineItem(
                    id=_new_id(),
                    variant_id=li.get("variant_id"),
                    product_id=li.get("product_id"),
                    title=li["title"],
                    quantity=li["quantity"],
                    price=Money(**li["price"]) if isinstance(li.get("price"), dict) else li["price"],
                )
                for li in data.line_items
            ],
            financial_status=data.financial_status,
            fulfillment_status=data.fulfillment_status,
            currency=data.currency,
            notes=data.notes,
            tags=data.tags,
            metadata=data.metadata,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_id(self, order_id: str) -> OrderDTO:
        entity = await self.repository.find_by_id(order_id)
        if entity is None:
            raise OrderNotFoundException(f"Order '{order_id}' was not found.")
        return self._to_dto(entity)

    async def list(
        self, page: int = 1, page_size: int = 20, store_id: str | None = None, customer_id: str | None = None
    ) -> PaginatedResultDTO[OrderDTO]:
        filters: dict = {}
        if store_id:
            filters["store_id"] = store_id
        if customer_id:
            filters["customer_id"] = customer_id
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[OrderDTO](
            items=[self._to_dto(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_status(self, order_id: str, data: OrderUpdateDTO) -> OrderDTO:
        entity = await self.repository.find_by_id(order_id)
        if entity is None:
            raise OrderNotFoundException(f"Order '{order_id}' was not found.")
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                setattr(entity, field, value)
        entity.audit.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def delete(self, order_id: str) -> bool:
        deleted = await self.repository.delete(order_id)
        if not deleted:
            raise OrderNotFoundException(f"Order '{order_id}' was not found.")
        return deleted

    @staticmethod
    def _to_dto(entity: Order) -> OrderDTO:
        return OrderDTO(
            id=entity.id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            customer_id=entity.customer_id,
            customer_email=entity.customer_email,
            line_items=[LineItemDTO(
                id=li.id,
                variant_id=li.variant_id,
                product_id=li.product_id,
                title=li.title,
                quantity=li.quantity,
                price=MoneyDTO(amount=str(li.price.amount), currency=li.price.currency) if hasattr(li.price, "amount") else MoneyDTO(amount="0", currency="USD"),
            ) for li in (entity.line_items or [])],
            financial_status=entity.financial_status,
            fulfillment_status=entity.fulfillment_status,
            currency=entity.currency,
            notes=entity.notes,
            tags=entity.tags,
            cancelled_at=entity.cancelled_at,
            audit=AuditInfoDTO(**entity.audit.model_dump()),
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class InventoryService:

    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    async def create(self, data: InventoryCreateDTO) -> InventoryDTO:
        entity = Inventory(
            id=_new_id(),
            product_id=data.product_id,
            variant_id=data.variant_id,
            store_id=data.store_id,
            org_id=data.org_id,
            external_id=data.external_id,
            quantity=data.quantity,
            available=data.available,
            committed=data.committed,
            incoming=data.incoming,
            location_id=data.location_id,
            location_name=data.location_name,
            low_stock_threshold=data.low_stock_threshold,
        )
        created = await self.repository.create(entity)
        return self._to_dto(created)

    async def get_by_variant(self, store_id: str, variant_id: str) -> InventoryDTO:
        entity = await self.repository.find_by_variant(store_id, variant_id)
        if entity is None:
            raise InventoryNotFoundException(f"Inventory for variant '{variant_id}' was not found.")
        return self._to_dto(entity)

    async def list(
        self, page: int = 1, page_size: int = 20, store_id: str | None = None
    ) -> PaginatedResultDTO[InventoryDTO]:
        filters: dict = {}
        if store_id:
            filters["store_id"] = store_id
        items, total = await self.repository.paginate(filters=filters, page=page, page_size=page_size)
        return PaginatedResultDTO[InventoryDTO](
            items=[self._to_dto(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, variant_id: str, data: InventoryUpdateDTO) -> InventoryDTO:
        items = await self.repository.find_many({"variant_id": variant_id})
        if not items:
            raise InventoryNotFoundException(f"Inventory for variant '{variant_id}' was not found.")
        entity = items[0]
        updates = data.model_dump(exclude_unset=True)
        for field, value in updates.items():
            if value is not None:
                setattr(entity, field, value)
        entity.audit.updated_at = datetime.now(UTC)
        updated = await self.repository.update(entity)
        return self._to_dto(updated)

    async def get_low_stock(self, store_id: str, threshold: int = 10) -> list[InventoryDTO]:
        items = await self.repository.find_low_stock(store_id, threshold)
        return [self._to_dto(item) for item in items]

    async def bulk_update(self, store_id: str, items: list[InventoryUpdateDTO]) -> int:
        count = 0
        for item in items:
            existing = await self.repository.find_many({"store_id": store_id})
            if existing:
                entity = existing[0]
                updates = item.model_dump(exclude_unset=True)
                for field, value in updates.items():
                    if value is not None:
                        setattr(entity, field, value)
                entity.audit.updated_at = datetime.now(UTC)
                await self.repository.update(entity)
                count += 1
        return count

    @staticmethod
    def _to_dto(entity: Inventory) -> InventoryDTO:
        return InventoryDTO(
            id=entity.id,
            product_id=entity.product_id,
            variant_id=entity.variant_id,
            store_id=entity.store_id,
            org_id=entity.org_id,
            external_id=entity.external_id,
            quantity=entity.quantity,
            available=entity.available,
            committed=entity.committed,
            incoming=entity.incoming,
            location_id=entity.location_id,
            location_name=entity.location_name,
            low_stock_threshold=entity.low_stock_threshold,
            audit=AuditInfoDTO(**entity.audit.model_dump()),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
