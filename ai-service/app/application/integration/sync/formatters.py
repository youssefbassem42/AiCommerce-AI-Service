from typing import Any, Optional


def _val(data: dict, key: str, default: str = "") -> str:
    v = data.get(key)
    if v is None:
        return default
    if isinstance(v, (list, dict)):
        return str(v)
    return str(v)


def format_product(data: dict) -> str:
    lines = [
        f"Product: {_val(data, 'title', '(no title)')}",
    ]
    if data.get("status"):
        lines.append(f"Status: {_val(data, 'status')}")
    if data.get("sku"):
        lines.append(f"SKU: {_val(data, 'sku')}")
    if data.get("price") is not None:
        lines.append(f"Price: {_val(data, 'price')}")
    if data.get("compare_at_price") is not None:
        lines.append(f"Compare at price: {_val(data, 'compare_at_price')}")
    if data.get("description"):
        lines.append(f"Description: {_val(data, 'description')}")
    if data.get("vendor"):
        lines.append(f"Vendor: {_val(data, 'vendor')}")
    if data.get("product_type"):
        lines.append(f"Type: {_val(data, 'product_type')}")
    if data.get("tags"):
        tags = _val(data, "tags")
        lines.append(f"Tags: {tags}")
    if data.get("weight") is not None:
        lines.append(f"Weight: {_val(data, 'weight')}")
    if data.get("inventory_quantity") is not None:
        lines.append(f"Inventory quantity: {_val(data, 'inventory_quantity')}")
    if data.get("image_url"):
        lines.append(f"Image: {_val(data, 'image_url')}")
    if data.get("category_id"):
        lines.append(f"Category: {_val(data, 'category_id')}")
    if data.get("handle"):
        lines.append(f"Handle: {_val(data, 'handle')}")
    return "\n".join(lines)


def format_order(data: dict) -> str:
    lines = [
        f"Order: {_val(data, 'external_id', '(no id)')}",
    ]
    if data.get("financial_status") or data.get("status"):
        lines.append(f"Status: {_val(data, 'financial_status') or _val(data, 'status')}")
    if data.get("fulfillment_status"):
        lines.append(f"Fulfillment: {_val(data, 'fulfillment_status')}")
    if data.get("email") or data.get("customer_email"):
        lines.append(f"Customer email: {_val(data, 'email') or _val(data, 'customer_email')}")
    if data.get("customer_id"):
        lines.append(f"Customer ID: {_val(data, 'customer_id')}")
    if data.get("subtotal") is not None:
        lines.append(f"Subtotal: {_val(data, 'subtotal')}")
    if data.get("total") is not None:
        lines.append(f"Total: {_val(data, 'total')}")
    if data.get("currency"):
        lines.append(f"Currency: {_val(data, 'currency')}")
    if data.get("shipping_price") is not None:
        lines.append(f"Shipping: {_val(data, 'shipping_price')}")
    if data.get("tax") is not None:
        lines.append(f"Tax: {_val(data, 'tax')}")
    if data.get("discount") is not None:
        lines.append(f"Discount: {_val(data, 'discount')}")
    if data.get("notes"):
        lines.append(f"Notes: {_val(data, 'notes')}")
    if data.get("tags"):
        lines.append(f"Tags: {_val(data, 'tags')}")
    return "\n".join(lines)


def format_customer(data: dict) -> str:
    first = _val(data, "first_name")
    last = _val(data, "last_name")
    name = f"{first} {last}".strip() or "(no name)"
    lines = [
        f"Customer: {name}",
    ]
    if data.get("email"):
        lines.append(f"Email: {_val(data, 'email')}")
    if data.get("phone"):
        lines.append(f"Phone: {_val(data, 'phone')}")
    if data.get("tags"):
        lines.append(f"Tags: {_val(data, 'tags')}")
    if data.get("accepts_marketing") is not None:
        lines.append(f"Accepts marketing: {_val(data, 'accepts_marketing')}")
    if data.get("notes"):
        lines.append(f"Notes: {_val(data, 'notes')}")
    return "\n".join(lines)


def format_dynamic(data: dict) -> str:
    """Fallback formatter — iterates all keys on the data dict to render text for any entity type."""
    lines: list[str] = []
    title = (
        data.get("title")
        or data.get("name")
        or data.get("external_id")
        or data.get("id")
        or "(unnamed)"
    )
    lines.append(f"{title}")
    for key, value in data.items():
        if key in ("external_id", "id", "title", "name"):
            continue
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


FORMATTER_MAP: dict[str, Any] = {
    "product": format_product,
    "order": format_order,
    "customer": format_customer,
}


def get_formatter(entity_type: str) -> Optional[Any]:
    formatter = FORMATTER_MAP.get(entity_type)
    if formatter is not None:
        return formatter
    return format_dynamic


def format_record(entity_type: str, data: dict) -> Optional[str]:
    formatter = get_formatter(entity_type)
    return formatter(data)
