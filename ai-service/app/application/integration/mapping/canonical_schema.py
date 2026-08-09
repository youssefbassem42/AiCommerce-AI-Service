"""Canonical entity schemas used as the reference contract for LLM-assisted
field mapping and deterministic validation of mapped records.

Every map target the LLM (or the rule engine) may produce must appear here.
Field definitions mirror the persisted Mongo documents
(``app.infrastructure.mongodb.documents``) plus the domain aggregates.
"""

from typing import Any

CANONICAL_SCHEMAS: dict[str, dict[str, Any]] = {
    "product": {
        "description": "A sellable item in the store catalog.",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "required": True,
                "description": (
                    "Product display title. Must never be empty; when the source omits title, "
                    "derive one from name or description."
                ),
            },
            {
                "name": "description",
                "type": "string",
                "required": False,
                "description": "Long description of the product.",
            },
            {"name": "handle", "type": "string", "required": False, "description": "URL-friendly slug."},
            {
                "name": "status",
                "type": "string",
                "required": False,
                "allowed": ["active", "draft", "archived"],
                "default": "active",
            },
            {
                "name": "product_type",
                "type": "string",
                "required": False,
                "description": "Product category type label.",
            },
            {"name": "vendor", "type": "string", "required": False, "description": "Vendor/brand name."},
            {"name": "tags", "type": "list[string]", "required": False},
            {
                "name": "price",
                "type": "money",
                "required": False,
                "description": "Money object: {amount: number, currency: 3-letter ISO code}.",
            },
            {
                "name": "compare_at_price",
                "type": "money",
                "required": False,
                "description": "Strikethrough/list price, same money shape.",
            },
            {"name": "sku", "type": "string", "required": False},
            {"name": "inventory_quantity", "type": "number", "required": False},
            {"name": "weight", "type": "number", "required": False},
            {"name": "image_url", "type": "string", "required": False, "description": "Primary image URL."},
            {
                "name": "images",
                "type": "array[object]",
                "required": False,
                "description": "List of images with url/alt_text.",
            },
            {"name": "category_id", "type": "string", "required": False},
            {
                "name": "external_id",
                "type": "string",
                "required": False,
                "description": "Stable ID from the source system.",
            },
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    "order": {
        "type": "object",
        "description": "A customer purchase order.",
        "fields": [
            {"name": "customer_id", "type": "string", "required": False},
            {"name": "customer_email", "type": "string", "required": False},
            {
                "name": "line_items",
                "type": "array[object]",
                "required": False,
                "description": "Items with id, title, quantity, price money, variant_id, product_id.",
            },
            {"name": "shipping_address", "type": "object", "required": False},
            {"name": "billing_address", "type": "object", "required": False},
            {"name": "subtotal_price", "type": "money", "required": False},
            {"name": "total_price", "type": "money", "required": False},
            {"name": "total_tax", "type": "money", "required": False},
            {"name": "total_discount", "type": "money", "required": False},
            {"name": "shipping_price", "type": "money", "required": False},
            {"name": "financial_status", "type": "string", "required": False, "default": "pending"},
            {"name": "fulfillment_status", "type": "string", "required": False},
            {
                "name": "currency",
                "type": "string",
                "required": False,
                "allowed": ["USD"],
                "description": "3-letter ISO code; default USD.",
            },
            {"name": "notes", "type": "string", "required": False},
            {"name": "tags", "type": "array[string]", "required": False},
            {"name": "external_id", "type": "string", "required": False},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    "customer": {
        "type": "object",
        "description": "A store customer.",
        "fields": [
            {"name": "email", "type": "string", "required": False},
            {"name": "first_name", "type": "string", "required": False},
            {"name": "last_name", "type": "string", "required": False},
            {"name": "phone", "type": "string", "required": False},
            {"name": "tags", "type": "array[string]", "required": False},
            {"name": "notes", "type": "string", "required": False},
            {"name": "accepts_marketing", "type": "boolean", "required": False, "default": False},
            {"name": "external_id", "type": "string", "required": False},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    "category": {
        "type": "object",
        "description": "A catalog category.",
        "fields": [
            {
                "name": "name",
                "type": "string",
                "required": True,
                "description": "Category display name. Must never be empty.",
            },
            {"name": "description", "type": "string", "required": False},
            {"name": "handle", "type": "string", "required": False},
            {"name": "parent_id", "type": "string", "required": False},
            {"name": "image_url", "type": "string", "required": False},
            {"name": "sort_order", "type": "number", "required": False, "default": 0},
            {"name": "external_id", "type": "string", "required": False},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
    "inventory": {
        "type": "object",
        "description": "Stock levels for a product variant at a location.",
        "fields": [
            {"name": "product_id", "type": "string", "required": True},
            {"name": "variant_id", "type": "string", "required": True},
            {"name": "quantity", "type": "number", "required": False},
            {"name": "available", "type": "number", "required": False},
            {"name": "committed", "type": "number", "required": False},
            {"name": "incoming", "type": "number", "required": False},
            {"name": "location_id", "type": "string", "required": False},
            {"name": "location_name", "type": "string", "required": False},
            {"name": "low_stock_threshold", "type": "number", "required": False},
            {"name": "external_id", "type": "string", "required": False},
            {"name": "metadata", "type": "object", "required": False},
        ],
    },
}

CANONICAL_ENTITY_TYPES = tuple(CANONICAL_SCHEMAS.keys())


def canonical_schema_for(entity_type: str) -> dict[str, Any] | None:
    return CANONICAL_SCHEMAS.get(entity_type)


def canonical_targets(entity_type: str) -> set[str]:
    schema = CANONICAL_SCHEMAS.get(entity_type)
    if not schema:
        return set()
    return {f["name"] for f in schema["fields"]}
