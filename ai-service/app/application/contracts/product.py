"""Canonical product payload for AI responses.

The shape produced here is what reaches the widget, the chat API, and any
downstream consumer. Convert domain DTOs (ProductCard, ScoredProduct) with
`product_card_to_payload`; never hand-assemble product dicts in routers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProductSpecPayload(BaseModel):
    name: str = ""
    value: str = ""
    category: str = "general"


class ProductPayload(BaseModel):
    product_id: str
    title: str
    price: str = ""
    currency: str = "USD"
    image_url: str | None = None
    product_url: str | None = None
    specs: list[ProductSpecPayload] = Field(default_factory=list)
    match_reasons: list[str] = Field(default_factory=list)


def product_card_to_payload(card: Any) -> ProductPayload | None:
    """Convert a domain product DTO (ProductCard/ScoredProduct) to the canonical payload."""
    product_id = getattr(card, "product_id", None)
    title = getattr(card, "title", None)
    if not product_id and not title:
        return None

    specs: list[ProductSpecPayload] = []
    for spec in getattr(card, "specs", None) or []:
        specs.append(
            ProductSpecPayload(
                name=str(getattr(spec, "name", None) or ""),
                value=str(getattr(spec, "value", None) or ""),
                category=str(getattr(spec, "category", "general") or "general"),
            )
        )

    return ProductPayload(
        product_id=str(product_id or ""),
        title=str(title or ""),
        price=str(getattr(card, "price", "") or ""),
        currency=str(getattr(card, "currency", "USD") or "USD"),
        image_url=getattr(card, "image_url", None),
        product_url=getattr(card, "product_url", None),
        specs=[s for s in specs if s.name or s.value][:12],
        match_reasons=list(getattr(card, "match_reasons", None) or [])[:6],
    )
