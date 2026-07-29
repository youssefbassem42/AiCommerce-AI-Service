from fastapi import APIRouter, Depends, HTTPException, Query, status

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
    CommerceDomainException,
    InventoryNotFoundException,
    OrderNotFoundException,
    ProductNotFoundException,
)

router = APIRouter(prefix="/api/v1/commerce", tags=["Commerce"])


def _handle_exception(exc: Exception) -> None:
    if isinstance(exc, (ProductNotFoundException, CategoryNotFoundException, OrderNotFoundException, InventoryNotFoundException)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, CommerceDomainException):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/products", response_model=ProductResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreateSchema,
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    try:
        result = await service.create(ProductCreateDTO(**payload.model_dump()))
        return ProductResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/products/{product_id}", response_model=ProductResponseSchema)
async def get_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    try:
        result = await service.get_by_id(product_id)
        return ProductResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/products", response_model=PaginatedResponseSchema)
async def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    service: ProductService = Depends(get_product_service),
) -> PaginatedResponseSchema:
    try:
        result = await service.list(page=page, page_size=page_size, store_id=store_id, status=status)
        return PaginatedResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.put("/products/{product_id}", response_model=ProductResponseSchema)
async def update_product(
    product_id: str,
    payload: ProductUpdateSchema,
    service: ProductService = Depends(get_product_service),
) -> ProductResponseSchema:
    try:
        result = await service.update(product_id, ProductUpdateDTO(**payload.model_dump(exclude_unset=True)))
        return ProductResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.delete("/products/{product_id}", response_model=DeleteResponseSchema)
async def delete_product(
    product_id: str,
    service: ProductService = Depends(get_product_service),
) -> DeleteResponseSchema:
    try:
        return DeleteResponseSchema(success=await service.delete(product_id))
    except Exception as exc:
        _handle_exception(exc)


@router.post("/categories", response_model=CategoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreateSchema,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    try:
        result = await service.create(CategoryCreateDTO(**payload.model_dump()))
        return CategoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/categories/{category_id}", response_model=CategoryResponseSchema)
async def get_category(
    category_id: str,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    try:
        result = await service.get_by_id(category_id)
        return CategoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/categories", response_model=PaginatedResponseSchema)
async def list_categories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str | None = Query(default=None),
    service: CategoryService = Depends(get_category_service),
) -> PaginatedResponseSchema:
    try:
        result = await service.list(page=page, page_size=page_size, store_id=store_id)
        return PaginatedResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.put("/categories/{category_id}", response_model=CategoryResponseSchema)
async def update_category(
    category_id: str,
    payload: CategoryUpdateSchema,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseSchema:
    try:
        result = await service.update(category_id, CategoryUpdateDTO(**payload.model_dump(exclude_unset=True)))
        return CategoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.delete("/categories/{category_id}", response_model=DeleteResponseSchema)
async def delete_category(
    category_id: str,
    service: CategoryService = Depends(get_category_service),
) -> DeleteResponseSchema:
    try:
        return DeleteResponseSchema(success=await service.delete(category_id))
    except Exception as exc:
        _handle_exception(exc)


@router.get("/categories/{category_id}/children", response_model=list[CategoryResponseSchema])
async def get_category_children(
    category_id: str,
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseSchema]:
    try:
        result = await service.get_children(category_id)
        return [CategoryResponseSchema(**item.model_dump()) for item in result]
    except Exception as exc:
        _handle_exception(exc)


@router.get("/categories/root/{store_id}", response_model=list[CategoryResponseSchema])
async def get_root_categories(
    store_id: str,
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseSchema]:
    try:
        result = await service.get_root_categories(store_id)
        return [CategoryResponseSchema(**item.model_dump()) for item in result]
    except Exception as exc:
        _handle_exception(exc)


@router.post("/orders", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreateSchema,
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    try:
        result = await service.create(OrderCreateDTO(**payload.model_dump()))
        return OrderResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/orders/{order_id}", response_model=OrderResponseSchema)
async def get_order(
    order_id: str,
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    try:
        result = await service.get_by_id(order_id)
        return OrderResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/orders", response_model=PaginatedResponseSchema)
async def list_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    service: OrderService = Depends(get_order_service),
) -> PaginatedResponseSchema:
    try:
        result = await service.list(page=page, page_size=page_size, store_id=store_id, customer_id=customer_id)
        return PaginatedResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.put("/orders/{order_id}/status", response_model=OrderResponseSchema)
async def update_order_status(
    order_id: str,
    payload: OrderUpdateStatusSchema,
    service: OrderService = Depends(get_order_service),
) -> OrderResponseSchema:
    try:
        result = await service.update_status(order_id, OrderUpdateDTO(**payload.model_dump(exclude_unset=True)))
        return OrderResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.post("/inventory", response_model=InventoryResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_inventory(
    payload: InventoryCreateSchema,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    try:
        result = await service.create(InventoryCreateDTO(**payload.model_dump()))
        return InventoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/inventory/{variant_id}", response_model=InventoryResponseSchema)
async def get_inventory(
    variant_id: str,
    store_id: str = Query(...),
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    try:
        result = await service.get_by_variant(store_id, variant_id)
        return InventoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/inventory", response_model=PaginatedResponseSchema)
async def list_inventory(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    store_id: str | None = Query(default=None),
    service: InventoryService = Depends(get_inventory_service),
) -> PaginatedResponseSchema:
    try:
        result = await service.list(page=page, page_size=page_size, store_id=store_id)
        return PaginatedResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.put("/inventory/{variant_id}", response_model=InventoryResponseSchema)
async def update_inventory(
    variant_id: str,
    payload: InventoryUpdateSchema,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryResponseSchema:
    try:
        result = await service.update(variant_id, InventoryUpdateDTO(**payload.model_dump(exclude_unset=True)))
        return InventoryResponseSchema(**result.model_dump())
    except Exception as exc:
        _handle_exception(exc)


@router.get("/inventory/low-stock/{store_id}", response_model=list[InventoryResponseSchema])
async def get_low_stock_inventory(
    store_id: str,
    threshold: int = Query(default=10, ge=1),
    service: InventoryService = Depends(get_inventory_service),
) -> list[InventoryResponseSchema]:
    try:
        result = await service.get_low_stock(store_id, threshold)
        return [InventoryResponseSchema(**item.model_dump()) for item in result]
    except Exception as exc:
        _handle_exception(exc)
