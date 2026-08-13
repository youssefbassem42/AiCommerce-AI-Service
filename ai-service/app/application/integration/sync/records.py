from typing import Any


def _money_amount(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value.amount)
    except (AttributeError, TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def product_to_record(entity: Any) -> dict[str, Any]:
    """Flatten a Product aggregate into the flat dict shape expected by format_record.

    Supports both variant-based products (ecommerce schema) and flat-schema stores
    where price/inventory live on the product itself.
    """
    variants = list(entity.variants or [])
    prices = [_money_amount(v.price) for v in variants if v.price is not None]
    prices = [p for p in prices if p is not None]
    flat_price = _money_amount(entity.price) if getattr(entity, "price", None) is not None else None
    inventory = (
        sum(int(v.inventory_quantity or 0) for v in variants)
        if variants
        else int(getattr(entity, "inventory_quantity", 0) or 0)
    )
    return {
        "_id": entity.id,
        "organization_id": entity.organization_id,
        "external_id": entity.external_id,
        "title": entity.title,
        "description": entity.description,
        "status": entity.status,
        "sku": variants[0].sku if variants else getattr(entity, "sku", None),
        "price": min(prices) if prices else flat_price,
        "currency": (
            (variants[0].price.currency if variants and variants[0].price is not None else None)
            or (getattr(entity.price, "currency", None) if getattr(entity, "price", None) is not None else None)
            or None
        ),
        "compare_at_price": (
            _money_amount(variants[0].compare_at_price)
            if variants and variants[0].compare_at_price is not None
            else None
        ),
        "inventory_quantity": inventory,
        "vendor": entity.vendor,
        "product_type": entity.product_type,
        "tags": list(entity.tags or []),
        "category_id": entity.category_id,
        "handle": entity.handle,
        "image_url": entity.images[0].url if (entity.images or []) else getattr(entity, "image_url", None),
    }


def category_to_record(entity: Any) -> dict[str, Any]:
    return {
        "_id": entity.id,
        "organization_id": entity.organization_id,
        "external_id": entity.external_id,
        "name": entity.name,
        "description": entity.description,
        "handle": entity.handle,
        "parent_id": entity.parent_id,
        "image_url": entity.image_url,
        "sort_order": entity.sort_order,
        "product_count": entity.product_count,
    }


def order_to_record(entity: Any) -> dict[str, Any]:
    return {
        "_id": entity.id,
        "organization_id": entity.organization_id,
        "external_id": entity.external_id,
        "customer_id": entity.customer_id,
        "customer_email": entity.customer_email,
        "subtotal_price": _money_amount(entity.subtotal_price),
        "total_price": _money_amount(entity.total_price),
        "total_tax": _money_amount(entity.total_tax),
        "total_discount": _money_amount(entity.total_discount),
        "shipping_price": _money_amount(entity.shipping_price),
        "financial_status": entity.financial_status,
        "fulfillment_status": entity.fulfillment_status,
        "currency": entity.currency,
        "notes": entity.notes,
        "tags": list(entity.tags or []),
    }
