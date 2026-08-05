from fastapi import APIRouter, Depends, Query, status

from app.api.auth.dependencies import (
    get_current_organization_id,
    get_current_store_id,
    require_admin_role,
)
from app.api.commerce.dependencies import (
    get_category_service,
    get_inventory_service,
    get_order_service,
    get_product_service,
)
from app.api.commerce.schemas import (
    CategoryCreateSchema,
    CategoryResponseSchema,
    CategoryUpdateSchema,
    DeleteResponseSchema,
    InventoryCreateSchema,
    InventoryResponseSchema,
    InventoryUpdateSchema,
    OrderCreateSchema,
    OrderResponseSchema,
    OrderUpdateStatusSchema,
    PaginatedResponseSchema,
    ProductCreateSchema,
    ProductResponseSchema,
    ProductUpdateSchema,
)
from app.application.commerce.dto.commerce_dto import (
    CategoryCreateDTO,
    CategoryUpdateDTO,
    InventoryCreateDTO,
    InventoryUpdateDTO,
    OrderCreateDTO,
    OrderUpdateDTO,
    ProductCreateDTO,
    ProductUpdateDTO,
)
from app.application.commerce.services import (
    CategoryService,
    InventoryService,
    OrderService,
    ProductService,
)
from app.domain.commerce.exceptions import (
    CategoryNotFoundException,
    InventoryNotFoundException,
    OrderNotFoundException,
    ProductNotFoundException,
)

router = APIRouter(
    prefix="/api/v1/commerce",
    tags=["Commerce"],
    dependencies=[Depends(require_admin_role)],
)


def _assert_store_owned(dto_store_id: str | None, store_id: str, not_found: Exception) -> None:
    """Fail-closed ownership check: an unscoped record (no store_id) is treated as not found."""
    if dto_store_id != store_id:
        raise not_found


@router.post("/products", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    data = payload.model_dump()
    data["store_id"] = store_id
    data["organization_id"] = organization_id
    result = await service.create(ProductCreateDTO(**data))
    return ProductResponseSchema(**result.model_dump())


@router.get("/products/{product_id}", response_model=ProductResponseSchema)
async def get_product(
    product_id: str,
    store_id: str = Depends(get_current_store_id),
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    result = await service.get_by_id(product_id)
    _assert_store_owned(result.store_id, store_id, ProductNotFoundException(f"Product '{product_id}' was not found."))
    return ProductResponseSchema(**result.model_dump())


@router.get("/products", response_model=PaginatedResponseSchema)
async def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    store_id: str = Depends(get_current_store_id),
    service: ProductService = Depends(get_product_service),
) -> PaginatedResponseSchema:
    result = await service.list(page=page, page_size=page_size, store_id=store_id, status=status)
    return PaginatedResponseSchema(**result.model_dump())


@router.put("/products/{product_id}", response_model=ProductResponseSchema)
async def update_product(
    product_id: str,
    payload: ProductUpdateSchema,
    store_id: str = Depends(get_current_store_id),
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    result = await service.get_by_id(product_id)
    _assert_store_owned(result.store_id, store_id, ProductNotFoundException(f"Product '{product_id}' was not found."))
    result = await service.update(product_id, ProductUpdateDTO(**payload.model_dump(exclude_unset=True)))
    return ProductResponseSchema(**result.model_dump())


@router.delete("/products/{product_id}", response_model=DeleteResponseSchema)
async def delete_product(
    product_id: str,
    store_id: str = Depends(get_current_store_id),
    service: ProductService = Depends(get_product_service),
) -> DeleteResponseSchema:
    result = await service.get_by_id(product_id)
    _assert_store_owned(result.store_id, store_id, ProductNotFoundException(f"Product '{product_id}' was not found."))
    return DeleteResponseSchema(success=await service.delete(product_id))


@router.post("/categories", response_model=CategoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreateSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    data = payload.model_dump()
    data["store_id"] = store_id
    data["org_id"] = organization_id
    result = await service.create(CategoryCreateDTO(**data))
    return CategoryResponseSchema(**result.model_dump())


@router.get("/categories/root", response_model=list[CategoryResponseSchema])
async def get_root_categories(
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseSchema]:
    result = await service.get_root_categories(store_id)
    return [CategoryResponseSchema(**item.model_dump()) for item in result]


@router.get("/categories/{category_id}", response_model=CategoryResponseSchema)
async def get_category(
    category_id: str,
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    result = await service.get_by_id(category_id)
    _assert_store_owned(
        result.store_id, store_id, CategoryNotFoundException(f"Category '{category_id}' was not found.")
    )
    return CategoryResponseSchema(**result.model_dump())


@router.get("/categories", response_model=PaginatedResponseSchema)
async def list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> PaginatedResponseSchema:
    result = await service.list(page=page, page_size=page_size, store_id=store_id)
    return PaginatedResponseSchema(**result.model_dump())


@router.put("/categories/{category_id}", response_model=CategoryResponseSchema)
async def update_category(
    category_id: str,
    payload: CategoryUpdateSchema,
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    result = await service.get_by_id(category_id)
    _assert_store_owned(
        result.store_id, store_id, CategoryNotFoundException(f"Category '{category_id}' was not found.")
    )
    result = await service.update(category_id, CategoryUpdateDTO(**payload.model_dump(exclude_unset=True)))
    return CategoryResponseSchema(**result.model_dump())


@router.delete("/categories/{category_id}", response_model=DeleteResponseSchema)
async def delete_category(
    category_id: str,
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> DeleteResponseSchema:
    result = await service.get_by_id(category_id)
    _assert_store_owned(
        result.store_id, store_id, CategoryNotFoundException(f"Category '{category_id}' was not found.")
    )
    return DeleteResponseSchema(success=await service.delete(category_id))


@router.get("/categories/{category_id}/children", response_model=list[CategoryResponseSchema])
async def get_category_children(
    category_id: str,
    store_id: str = Depends(get_current_store_id),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseSchema]:
    parent = await service.get_by_id(category_id)
    _assert_store_owned(
        parent.store_id, store_id, CategoryNotFoundException(f"Category '{category_id}' was not found.")
    )
    result = await service.get_children(category_id)
    return [CategoryResponseSchema(**item.model_dump()) for item in result]


@router.post("/orders", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    data = payload.model_dump()
    data["store_id"] = store_id
    data["org_id"] = organization_id
    result = await service.create(OrderCreateDTO(**data))
    return OrderResponseSchema(**result.model_dump())


@router.get("/orders/{order_id}", response_model=OrderResponseSchema)
async def get_order(
    order_id: str,
    store_id: str = Depends(get_current_store_id),
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    result = await service.get_by_id(order_id)
    _assert_store_owned(result.store_id, store_id, OrderNotFoundException(f"Order '{order_id}' was not found."))
    return OrderResponseSchema(**result.model_dump())


@router.get("/orders", response_model=PaginatedResponseSchema)
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    customer_id: str | None = Query(default=None),
    store_id: str = Depends(get_current_store_id),
    service: OrderService = Depends(get_order_service),
) -> PaginatedResponseSchema:
    result = await service.list(page=page, page_size=page_size, store_id=store_id, customer_id=customer_id)
    return PaginatedResponseSchema(**result.model_dump())


@router.put("/orders/{order_id}/status", response_model=OrderResponseSchema)
async def update_order_status(
    order_id: str,
    payload: OrderUpdateStatusSchema,
    store_id: str = Depends(get_current_store_id),
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    existing = await service.get_by_id(order_id)
    _assert_store_owned(existing.store_id, store_id, OrderNotFoundException(f"Order '{order_id}' was not found."))
    result = await service.update_status(order_id, OrderUpdateDTO(**payload.model_dump(exclude_unset=True)))
    return OrderResponseSchema(**result.model_dump())


@router.post("/inventory", response_model=InventoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_inventory(
    payload: InventoryCreateSchema,
    store_id: str = Depends(get_current_store_id),
    organization_id: str = Depends(get_current_organization_id),
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    data = payload.model_dump()
    data["store_id"] = store_id
    data["org_id"] = organization_id
    result = await service.create(InventoryCreateDTO(**data))
    return InventoryResponseSchema(**result.model_dump())


@router.get("/inventory/low-stock", response_model=list[InventoryResponseSchema])
async def get_low_stock_inventory(
    threshold: int = Query(default=10, ge=1),
    store_id: str = Depends(get_current_store_id),
    service: InventoryService = Depends(get_inventory_service),
) -> list[InventoryResponseSchema]:
    result = await service.get_low_stock(store_id, threshold)
    return [InventoryResponseSchema(**item.model_dump()) for item in result]


@router.get("/inventory/{variant_id}", response_model=InventoryResponseSchema)
async def get_inventory(
    variant_id: str,
    store_id: str = Depends(get_current_store_id),
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    result = await service.get_by_variant(store_id, variant_id)
    return InventoryResponseSchema(**result.model_dump())


@router.get("/inventory", response_model=PaginatedResponseSchema)
async def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str = Depends(get_current_store_id),
    service: InventoryService = Depends(get_inventory_service),
) -> PaginatedResponseSchema:
    result = await service.list(page=page, page_size=page_size, store_id=store_id)
    return PaginatedResponseSchema(**result.model_dump())


@router.put("/inventory/{variant_id}", response_model=InventoryResponseSchema)
async def update_inventory(
    variant_id: str,
    payload: InventoryUpdateSchema,
    store_id: str = Depends(get_current_store_id),
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    existing = await service.get_by_variant(store_id, variant_id)
    _assert_store_owned(
        existing.store_id,
        store_id,
        InventoryNotFoundException(f"Inventory for variant '{variant_id}' was not found."),
    )
    result = await service.update(variant_id, InventoryUpdateDTO(**payload.model_dump(exclude_unset=True)))
    return InventoryResponseSchema(**result.model_dump())
