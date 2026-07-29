from fastapi import Depends

from app.application.commerce.services import (
    CategoryService,
    InventoryService,
    OrderService,
    ProductService,
)
from app.infrastructure.mongodb.repositories.commerce_category_repository import (
    CommerceCategoryRepository,
)
from app.infrastructure.mongodb.repositories.commerce_inventory_repository import (
    CommerceInventoryRepository,
)
from app.infrastructure.mongodb.repositories.commerce_order_repository import (
    CommerceOrderRepository,
)
from app.infrastructure.mongodb.repositories.commerce_product_repository import (
    CommerceProductRepository,
)


def get_product_repository() -> CommerceProductRepository:
    return CommerceProductRepository()


def get_category_repository() -> CommerceCategoryRepository:
    return CommerceCategoryRepository()


def get_order_repository() -> CommerceOrderRepository:
    return CommerceOrderRepository()


def get_inventory_repository() -> CommerceInventoryRepository:
    return CommerceInventoryRepository()


def get_product_service(
    repository: CommerceProductRepository = Depends(get_product_repository),
) -> ProductService:
    return ProductService(repository=repository)


def get_category_service(
    repository: CommerceCategoryRepository = Depends(get_category_repository),
) -> CategoryService:
    return CategoryService(repository=repository)


def get_order_service(
    repository: CommerceOrderRepository = Depends(get_order_repository),
) -> OrderService:
    return OrderService(repository=repository)


def get_inventory_service(
    repository: CommerceInventoryRepository = Depends(get_inventory_repository),
) -> InventoryService:
    return InventoryService(repository=repository)
