import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.mongodb.collections import (
    get_categories_collection,
    get_customers_collection,
    get_entities_collection,
    get_inventory_collection,
    get_orders_collection,
    get_products_collection,
)

logger = logging.getLogger(__name__)


class EntityWriter(ABC):
    @abstractmethod
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool: ...

    @abstractmethod
    def collection_name(self) -> str: ...


class ProductWriter(EntityWriter):
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_products_collection()
        now = datetime.now(UTC)
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "external_id": external_id,
            "title": data.get("title", ""),
            "description": data.get("description"),
            "handle": data.get("handle"),
            "status": data.get("status", "active"),
            "product_type": data.get("product_type"),
            "vendor": data.get("vendor"),
            "tags": data.get("tags", []),
            "price": data.get("price"),
            "compare_at_price": data.get("compare_at_price"),
            "sku": data.get("sku"),
            "inventory_quantity": data.get("inventory_quantity", 0),
            "weight": data.get("weight"),
            "image_url": data.get("image_url"),
            "category_id": data.get("category_id"),
            "metadata": data.get("metadata", {}),
            "updated_at": now,
        }
        for key in ("created_at", "updated_at", "deleted_at"):
            doc.pop(key, None)
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "products"


class OrderWriter(EntityWriter):
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_orders_collection()
        now = datetime.now(UTC)
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "external_id": external_id,
            "customer_id": data.get("customer_id"),
            "customer_email": data.get("email") or data.get("customer_email"),
            "line_items": data.get("line_items", []),
            "shipping_address": data.get("shipping_address"),
            "billing_address": data.get("billing_address"),
            "subtotal_price": data.get("subtotal"),
            "total_price": data.get("total"),
            "total_tax": data.get("tax"),
            "total_discount": data.get("discount"),
            "shipping_price": data.get("shipping_price"),
            "financial_status": data.get("financial_status") or data.get("status"),
            "fulfillment_status": data.get("fulfillment_status"),
            "currency": data.get("currency", "USD"),
            "notes": data.get("notes"),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "updated_at": now,
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "orders"


class CustomerWriter(EntityWriter):
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_customers_collection()
        now = datetime.now(UTC)
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "external_id": external_id,
            "email": data.get("email"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "phone": data.get("phone"),
            "tags": data.get("tags", []),
            "notes": data.get("notes"),
            "accepts_marketing": data.get("accepts_marketing", False),
            "metadata": data.get("metadata", {}),
            "updated_at": now,
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "customers"


class CategoryWriter(EntityWriter):
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_categories_collection()
        now = datetime.now(UTC)
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "external_id": external_id,
            "name": data.get("name", ""),
            "description": data.get("description"),
            "handle": data.get("handle"),
            "parent_id": data.get("parent_id"),
            "image_url": data.get("image_url"),
            "sort_order": data.get("sort_order", 0),
            "metadata": data.get("metadata", {}),
            "updated_at": now,
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "categories"


class InventoryWriter(EntityWriter):
    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_inventory_collection()
        now = datetime.now(UTC)
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "external_id": external_id,
            "product_id": data.get("product_id") or data.get("external_id"),
            "variant_id": data.get("variant_id"),
            "quantity": data.get("inventory_quantity", 0),
            "available": data.get("available", data.get("inventory_quantity", 0)),
            "committed": data.get("committed", 0),
            "incoming": data.get("incoming", 0),
            "location_id": data.get("location_id"),
            "location_name": data.get("location_name"),
            "low_stock_threshold": data.get("low_stock_threshold"),
            "metadata": data.get("metadata", {}),
            "updated_at": now,
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "inventory"


class DynamicEntityWriter(EntityWriter):
    """Schema-agnostic writer that stores any entity type in the unified
    ``entities`` collection, preserving every field from the source data dict."""

    def __init__(self, entity_type: str = "unknown"):
        self._entity_type = entity_type

    async def upsert(self, store_id: str, org_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_entities_collection()
        now = datetime.now(UTC)
        cleaned_data = {
            k: v for k, v in data.items() if k not in ("created_at", "updated_at", "deleted_at", "synced_at")
        }
        doc = {
            "store_id": store_id,
            "organization_id": org_id,
            "entity_type": self._entity_type,
            "external_id": external_id,
            "data": cleaned_data,
            "synced_at": now,
            "updated_at": now,
        }
        for key in ("created_at", "updated_at", "deleted_at", "synced_at"):
            doc.pop(key, None)
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "entities"


WRITER_MAP: dict[str, EntityWriter] = {
    "product": ProductWriter(),
    "order": OrderWriter(),
    "customer": CustomerWriter(),
    "category": CategoryWriter(),
    "inventory": InventoryWriter(),
}


def get_writer(entity_type: str) -> EntityWriter | None:
    writer = WRITER_MAP.get(entity_type)
    if writer is not None:
        return writer
    logger.info("No dedicated writer for '%s' — using DynamicEntityWriter.", entity_type)
    return DynamicEntityWriter(entity_type=entity_type)
