"""Canonical bundle payload for AI responses.

Convert domain bundle candidates with `bundle_payload_from_candidates`; the
first within-budget candidate is used, mirroring the previous serializer
behavior exactly (shape preserved, source consolidated).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BundleItemPayload(BaseModel):
    product_id: str
    title: str = ""
    original_price: str = ""
    discount_pct: float = 0.0
    price_after_discount: str = ""
    product_url: str | None = None
    image_url: str | None = None


class BundlePayload(BaseModel):
    items: list[BundleItemPayload] = Field(default_factory=list)
    total_original: str = ""
    total_discount: str = ""
    promo_code: str | None = None
    currency: str = "USD"
    within_budget: bool = True


def _bundle_item(candidate_item: Any) -> BundleItemPayload:
    return BundleItemPayload(
        product_id=str(getattr(candidate_item, "product_id", "") or ""),
        title=str(getattr(candidate_item, "product_title", "") or ""),
        original_price=str(getattr(candidate_item, "original_price", "") or ""),
        discount_pct=float(getattr(candidate_item, "discount_pct", 0.0) or 0.0),
        price_after_discount=str(getattr(candidate_item, "price_after_discount", "") or ""),
        product_url=getattr(candidate_item, "product_url", None),
        image_url=getattr(candidate_item, "image_url", None),
    )


def bundle_payload_from_candidates(bundles: list[Any]) -> BundlePayload | None:
    """First within-budget bundle candidate (or the first candidate) as the canonical payload."""
    candidates = [b for b in bundles if getattr(b, "within_budget", True)] or list(bundles)
    if not candidates:
        return None
    candidate = candidates[0]

    return BundlePayload(
        items=[_bundle_item(item) for item in getattr(candidate, "products", None) or []],
        total_original=str(getattr(candidate, "total_original", "") or ""),
        total_discount=str(getattr(candidate, "total_discount", "") or ""),
        promo_code=getattr(candidate, "promo_code", None),
        currency=str(getattr(candidate, "currency", "USD") or "USD"),
        within_budget=bool(getattr(candidate, "within_budget", True)),
    )
