import logging
import re
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


def _normalize_currency(value: Any, fallback: str = "USD") -> str:
    if isinstance(value, str) and len(value) == 3 and value.isalpha():
        return value.upper()
    return fallback


def _coerce_str(value: Any) -> str | None:
    """Coerce a scalar/array API value into a plain string (or None).

    Some endpoints return single-element arrays for string fields
    (e.g. ``firstName: ["mouren mohsen"]``); those are joined so the
    document still satisfies the collection's string|null schema.
    """
    if value is None or value == "":
        return None
    if isinstance(value, list):
        parts = [str(v) for v in value if v is not None and v != ""]
        if not parts:
            return None
        value = " ".join(parts)
    return str(value) if value is not None else None


def _normalize_money(value: Any) -> dict[str, Any] | None:
    """Coerce API money shapes (dict amount, number, numeric string) into {amount, currency}."""
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        amount = value.get("amount", value.get("value", 0))
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return None
        return {
            "amount": max(0.0, amount),
            "currency": _normalize_currency(value.get("currency", "USD")),
        }
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return {"amount": max(0.0, amount), "currency": "USD"}


def _normalize_line_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item = dict(item)
        price = item.get("price")
        if isinstance(price, (dict, int, float, str)):
            item["price"] = _normalize_money(price)
        tax_lines = item.get("tax_lines")
        if isinstance(tax_lines, list):
            clean_tax_lines = []
            for tax_line in tax_lines:
                if isinstance(tax_line, dict):
                    tax_line = dict(tax_line)
                    tax_price = tax_line.get("price")
                    if isinstance(tax_price, (dict, int, float, str)):
                        tax_line["price"] = _normalize_money(tax_price)
                clean_tax_lines.append(tax_line)
            item["tax_lines"] = clean_tax_lines
        normalized.append(item)
    return normalized


def _audit_set(now: datetime) -> dict[str, Any]:
    return {"updated_at": now, "audit.updated_at": now}


def _audit_set_on_insert(now: datetime) -> dict[str, Any]:
    return {"created_at": now, "audit.created_at": now, "audit.updated_by": None}


class EntityWriter(ABC):
    @abstractmethod
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool: ...

    @abstractmethod
    def collection_name(self) -> str: ...


class ProductWriter(EntityWriter):
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_products_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        category_id = data.get("category_id") or data.get("categoryId")
        if not category_id:
            category_id = await self._resolve_category_id(store_id, data)
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
            "external_id": external_id,
            "title": data.get("title") or data.get("name") or "",
            "description": data.get("description"),
            "handle": data.get("handle"),
            "status": data.get("status", "active"),
            "product_type": data.get("product_type"),
            "vendor": data.get("vendor"),
            "tags": data.get("tags", []),
            "price": _normalize_money(data.get("price")),
            "compare_at_price": _normalize_money(data.get("compare_at_price")),
            "sku": data.get("sku"),
            "inventory_quantity": data.get("inventory_quantity") or data.get("stockQuantity") or 0,
            "weight": data.get("weight"),
            "image_url": data.get("image_url") or data.get("imageUrl"),
            "category_id": category_id,
            "metadata": data.get("metadata", {}),
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {
                "$set": {**doc, **_audit_set(now)},
                "$setOnInsert": _audit_set_on_insert(now),
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    @staticmethod
    async def _resolve_category_id(store_id: str, data: dict[str, Any]) -> Any:
        """Resolve a product's category from the category *name* when the API
        omits ``categoryId`` on the list endpoint (e.g. only ``categoryName``).

        Matches against the synced categories of the same store and returns
        the category's ``external_id`` so products and categories share the
        same reference.
        """
        name = data.get("category_name") or data.get("product_type")
        if not name or not isinstance(name, str):
            return None
        collection = get_categories_collection()
        category = await collection.find_one({"store_id": store_id, "name": name})
        if category is None:
            escaped = re.escape(name)
            category = await collection.find_one(
                {"store_id": store_id, "name": {"$regex": f"^{escaped}$", "$options": "i"}}
            )
        if category is None:
            return None
        return str(category.get("external_id") or category.get("_id"))

    def collection_name(self) -> str:
        return "products"


class OrderWriter(EntityWriter):
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_orders_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
            "external_id": external_id,
            "customer_id": data.get("customer_id"),
            "customer_email": _coerce_str(data.get("email") or data.get("customer_email")),
            "line_items": _normalize_line_items(data.get("line_items", [])),
            "shipping_address": data.get("shipping_address"),
            "billing_address": data.get("billing_address"),
            "subtotal_price": _normalize_money(data.get("subtotal")),
            "total_price": _normalize_money(data.get("total")),
            "total_tax": _normalize_money(data.get("tax")),
            "total_discount": _normalize_money(data.get("discount")),
            "shipping_price": _normalize_money(data.get("shipping_price")),
            "financial_status": data.get("financial_status") or data.get("status"),
            "fulfillment_status": data.get("fulfillment_status"),
            "currency": _normalize_currency(data.get("currency", "USD")),
            "notes": data.get("notes"),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {
                "$set": {**doc, **_audit_set(now)},
                "$setOnInsert": _audit_set_on_insert(now),
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "orders"


class CustomerWriter(EntityWriter):
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_customers_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
            "external_id": external_id,
            "email": _coerce_str(data.get("email")),
            "first_name": _coerce_str(data.get("first_name")),
            "last_name": _coerce_str(data.get("last_name")),
            "phone": _coerce_str(data.get("phone")),
            "tags": data.get("tags", []),
            "notes": data.get("notes"),
            "accepts_marketing": data.get("accepts_marketing", False),
            "metadata": data.get("metadata", {}),
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {
                "$set": {**doc, **_audit_set(now)},
                "$setOnInsert": _audit_set_on_insert(now),
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "customers"


class CategoryWriter(EntityWriter):
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_categories_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
            "external_id": external_id,
            "name": data.get("name", ""),
            "description": data.get("description"),
            "handle": data.get("handle"),
            "parent_id": data.get("parent_id"),
            "image_url": data.get("image_url"),
            "sort_order": data.get("sort_order", 0),
            "metadata": data.get("metadata", {}),
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {
                "$set": {**doc, **_audit_set(now)},
                "$setOnInsert": _audit_set_on_insert(now),
            },
            upsert=True,
        )
        return result.upserted_id is not None or result.modified_count > 0

    def collection_name(self) -> str:
        return "categories"


class InventoryWriter(EntityWriter):
    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_inventory_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
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
        }
        result = await collection.update_one(
            {"store_id": store_id, "external_id": external_id},
            {
                "$set": {**doc, **_audit_set(now)},
                "$setOnInsert": _audit_set_on_insert(now),
            },
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

    async def upsert(self, store_id: str, organization_id: str, external_id: str, data: dict[str, Any]) -> bool:
        collection = get_entities_collection()
        now = datetime.now(UTC)
        organization_id = organization_id or store_id
        cleaned_data = {
            k: v for k, v in data.items() if k not in ("created_at", "updated_at", "deleted_at", "synced_at")
        }
        doc = {
            "store_id": store_id,
            "organization_id": organization_id,
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
