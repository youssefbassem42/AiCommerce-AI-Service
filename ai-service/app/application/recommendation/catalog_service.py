"""Deterministic recommendation business service (Phase 4).

Pipeline:

    requirements
     ↓
    catalog
     ↓
    hard filters
     ↓
    candidate products
     ↓
    ranking
     ↓
    discount strategy

All math is deterministic — the LLM never computes prices, discounts, or
matches. The LLM only parses the intent (Fix 4.1) and explains the final
structured result (Fix 4.5).
"""

import logging
import re
from decimal import Decimal
from typing import Any

from app.application.recommendation.dto.recommendation_dto import (
    ProductSpecValue,
    RecommendationIntent,
    ScoredProduct,
)
from app.domain.commerce.aggregates.product import Product
from app.domain.commerce.repositories import ProductRepository

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = 30

# Component weights for Fix 4.3 ranking, in priority order:
# category > spec > budget fit > use case > brand > availability.
_RANKING_WEIGHTS = {
    "category": 0.30,
    "spec": 0.25,
    "budget": 0.20,
    "use_case": 0.10,
    "brand": 0.10,
    "availability": 0.05,
}

# Option-style requirements that can be verified against catalog option
# values / variant titles / tags. Everything else is checked by token
# presence and only ever excludes on a provable contradiction.
_VERIFIABLE_SPEC_NAMES = ("color", "size", "material", "finish", "capacity")


def _spec_name_value(spec: Any) -> tuple[str | None, str | None]:
    """Read a requirement from either supported shape.

    Legacy LLM output uses {"ram": ">= 16GB"} (name -> value); the canonical
    form uses {"name": "ram", "value": ">= 16GB"}.
    """
    if not isinstance(spec, dict) or not spec:
        return None, None
    if "name" in spec:
        return spec.get("name"), spec.get("value")
    name, value = next(iter(spec.items()))
    return name, value


class RecommendationCatalogService:
    """Deterministic retrieval, ranking, and discount math (Fixes 4.2-4.4)."""

    @classmethod
    async def retrieve_candidates(
        cls,
        intent: RecommendationIntent,
        store_id: str,
        product_repo: ProductRepository,
        limit: int = _MAX_CANDIDATES,
    ) -> list[Product]:
        """Requirements -> catalog -> hard filters -> candidate products (Fix 4.2).

        Retrieval is semantic but deterministic:

        1. Taxonomy retrieval — the parsed category phrase is resolved against
           the store's own product taxonomy values (``product_type`` and
           ``category_id`` distinct values). The catalog stores category names
           on ``product_type`` (e.g. "Electronics"), so "electronics" matches
           records whose taxonomy says "Electronics"; "home appliances"
           matches "Home Appliances". Records that carry no ``product_type``
           but a ``category_id`` are still reachable through the category
           reference.
        2. Product-title matching — only when taxonomy retrieval provided no
           candidates, the escaped phrase is matched against product titles
           ("laptop" -> "Gaming Laptop RTX"). Bounded, meaningful, and never
           a regex across every field.

        Hard constraints applied to both sets: store, availability, category,
        price, and explicit user requirements (brand, option-style specs,
        attributes). Every candidate set is store-scoped.
        """
        if not intent.product_type:
            return []

        base_filters: dict[str, Any] = {
            "store_id": store_id,
            "status": "active",
        }
        if intent.brand:
            base_filters["vendor"] = {"$regex": re.escape(intent.brand.strip()), "$options": "i"}

        phrase = intent.product_type.strip()
        products: list[Product] = []
        source = "none"

        try:
            type_keys, category_keys = await cls._resolve_taxonomy_keys(phrase, store_id, product_repo)
            if type_keys or category_keys:
                or_conditions: list[dict[str, Any]] = []
                if type_keys:
                    or_conditions.append({"product_type": {"$in": type_keys}})
                if category_keys:
                    or_conditions.append({"category_id": {"$in": category_keys}})
                products = await cls._find_products(product_repo, {**base_filters, "$or": or_conditions}, limit)
                source = "taxonomy"
        except Exception:
            logger.warning("Taxonomy retrieval failed (store=%s)", store_id, exc_info=True)

        if not products:
            try:
                products = await cls._find_products(
                    product_repo,
                    {**base_filters, "title": {"$regex": re.escape(phrase), "$options": "i"}},
                    limit,
                )
                source = "title"
            except Exception:
                logger.warning("Title retrieval failed (store=%s)", store_id, exc_info=True)
                return []

        budget = Decimal(str(intent.max_budget)) if intent.max_budget is not None else None

        candidates: list[Product] = []
        for product in products:
            if not _product_available(product):
                continue
            price = _product_price(product)
            if price is None or price <= 0:
                continue
            if budget is not None and price > budget and not _discountable_to_budget(product, budget):
                continue
            if not cls._meets_explicit_requirements(product, intent):
                continue
            candidates.append(product)

        logger.info(
            "catalog_retrieval store=%s intent=%s source=%s fetched=%d candidates=%d budget=%s brand=%s",
            store_id,
            phrase,
            source,
            len(products),
            len(candidates),
            budget,
            intent.brand,
        )
        return candidates

    @staticmethod
    async def _find_products(
        product_repo: ProductRepository,
        filters: dict[str, Any],
        limit: int,
    ) -> list[Product]:
        try:
            products = await product_repo.find_many(filters, limit=limit)
        except Exception:
            logger.warning("Deterministic catalog retrieval failed", exc_info=True)
            return []
        if not isinstance(products, list):
            logger.warning("Catalog repository returned unexpected type: %s", type(products).__name__)
            return []
        return products

    @classmethod
    async def _resolve_taxonomy_keys(
        cls,
        phrase: str,
        store_id: str,
        product_repo: ProductRepository,
    ) -> tuple[list[str], list[str]]:
        """Resolve a parsed category phrase against the store's taxonomy values.

        Returns ``(product_type_keys, category_id_keys)`` — the real values
        present on the store's product records that the phrase refers to.
        Exact, containment (plural/suffix), and shared-token matches qualify;
        the phrase never matches values it has no semantic relation to.
        """
        type_keys: list[str] = []
        category_keys: list[str] = []
        for field in ("product_type", "category_id"):
            try:
                values = await product_repo.distinct_field_values(store_id, field)
            except Exception:
                logger.debug("distinct_field_values failed for '%s' (store=%s)", field, store_id, exc_info=True)
                continue
            if not isinstance(values, list):
                continue
            keys = [v for v in values if isinstance(v, str) and _taxonomy_match(phrase, v)]
            if field == "product_type":
                type_keys = keys
            else:
                category_keys = keys
        return type_keys, category_keys

    @classmethod
    def build_scored_candidates(cls, products: list[Product]) -> list[ScoredProduct]:
        """Convert verified catalog records into priced, stock-aware candidates.

        Catalog candidates are authoritative: price/stock/specs come from the
        Mongo record, never from a search payload, so they skip the
        find_by_id re-resolution in the filter stage (price_resolved=True).
        """
        scored: list[ScoredProduct] = []
        for product in products:
            price = _product_price(product)
            if price is None:
                continue
            scored.append(
                ScoredProduct(
                    product_id=product.id,
                    store_id=product.store_id,
                    title=product.title,
                    description=product.description,
                    price=price,
                    currency=_product_currency(product) or "USD",
                    image_url=_first_image_url(product),
                    product_url=product.handle,
                    specs=_product_specs(product),
                    in_stock=_product_available(product),
                    stock_quantity=_stock_quantity(product),
                    max_discount_pct=_max_discount_pct(product),
                    price_resolved=True,
                )
            )
        return scored

    @classmethod
    def rank_candidates(
        cls,
        candidates: list[ScoredProduct],
        intent: RecommendationIntent,
    ) -> list[ScoredProduct]:
        """Deterministic ranking (Fix 4.3).

        Ranked by weighted category match, spec match, budget fit, use case,
        brand preference, and availability. Ties break on price (cheaper
        first), then on the vector search score when present.
        """
        ranked: list[ScoredProduct] = []
        for candidate in candidates:
            category_score = _category_match(candidate, intent)
            spec_score = _spec_match(candidate, intent)
            budget_score = _budget_fit(candidate, intent)
            use_case_score = _use_case_match(candidate, intent)
            brand_score = _brand_match(candidate, intent)
            availability_score = _availability_score(candidate)

            total = (
                _RANKING_WEIGHTS["category"] * category_score
                + _RANKING_WEIGHTS["spec"] * spec_score
                + _RANKING_WEIGHTS["budget"] * budget_score
                + _RANKING_WEIGHTS["use_case"] * use_case_score
                + _RANKING_WEIGHTS["brand"] * brand_score
                + _RANKING_WEIGHTS["availability"] * availability_score
            )
            candidate.score = round(total, 4)
            candidate.match_reasons = _build_match_reasons(
                candidate,
                intent,
                category_score,
                spec_score,
                budget_score,
                use_case_score,
                brand_score,
            )
            ranked.append(candidate)

        ranked.sort(key=lambda p: (-p.score, float(p.price), -p.match_score))
        for index, candidate in enumerate(ranked):
            candidate.rank = index + 1
        return ranked

    @classmethod
    def apply_discount_strategy(
        cls,
        candidates: list[ScoredProduct],
        budget: float | None,
    ) -> list[ScoredProduct]:
        """Normal price -> budget comparison -> max discount -> final price (Fix 4.4).

        Deterministic. Only a product whose maximum allowed discount brings
        its price within budget is marked discount_available; the applied
        discount never exceeds the product's max_discount_pct.
        """
        for candidate in candidates:
            price = candidate.price
            if budget is None or price is None or price <= 0:
                continue
            budget_decimal = Decimal(str(budget))
            if price <= budget_decimal:
                continue
            max_pct = Decimal(str(candidate.max_discount_pct or 0))
            if max_pct <= 0:
                continue
            final_price = (price * (Decimal("1") - max_pct / Decimal("100"))).quantize(Decimal("0.01"))
            if final_price <= budget_decimal:
                candidate.discount_pct = float(max_pct)
                candidate.discount_available = True
                candidate.final_price = final_price
        return candidates

    @staticmethod
    def _meets_explicit_requirements(product: Product, intent: RecommendationIntent) -> bool:
        """Hard filter: drop products that provably contradict an explicit requirement.

        A product that merely lacks the attribute passes; a product that
        contradicts the requirement (brand mismatch, conflicting option value)
        is excluded.
        """
        if intent.brand:
            vendor = (product.vendor or "").strip().lower()
            if vendor and intent.brand.strip().lower() not in vendor:
                return False

        for spec in intent.required_specs:
            name, value = _spec_name_value(spec)
            name_lower = (name or "").strip().lower()
            value_lower = str(value or "").strip().lower()
            if not value_lower or value_lower in ("any", "none", "no preference"):
                continue
            if name_lower in ("brand", "vendor"):
                vendor = (product.vendor or "").strip().lower()
                if vendor and value_lower not in vendor:
                    return False
            elif name_lower in _VERIFIABLE_SPEC_NAMES:
                known_values = _option_values(product, name_lower)
                if known_values and value_lower not in known_values:
                    return False
        return True


def _product_available(product: Product) -> bool:
    variants = list(product.variants or [])
    if variants:
        return any(v.inventory_quantity > 0 for v in variants)
    return int(getattr(product, "inventory_quantity", 0) or 0) > 0


def _stock_quantity(product: Product) -> int:
    variants = list(product.variants or [])
    if variants:
        return sum(int(v.inventory_quantity or 0) for v in variants)
    return int(getattr(product, "inventory_quantity", 0) or 0)


def _product_price(product: Product) -> Decimal | None:
    """Lowest in-stock variant price; falls back to the flat-schema price."""
    variants = list(product.variants or [])
    prices = [v.price.amount for v in variants if v.price is not None and v.inventory_quantity > 0]
    if not prices and variants:
        prices = [v.price.amount for v in variants if v.price is not None]
    if prices:
        return min(prices)
    flat = getattr(product, "price", None)
    if flat is not None and flat.amount is not None:
        return flat.amount
    return None


def _product_currency(product: Product) -> str | None:
    variants = list(product.variants or [])
    if variants:
        for variant in variants:
            if variant.price is not None:
                return variant.price.currency
        return None
    flat = getattr(product, "price", None)
    if flat is not None:
        return flat.currency
    return None


def _max_discount_pct(product: Product) -> float:
    try:
        return float(product.metadata.get("max_discount_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _discountable_to_budget(product: Product, budget: Decimal) -> bool:
    """True when the max allowed discount brings the price within budget."""
    price = _product_price(product)
    if price is None:
        return False
    max_pct = _max_discount_pct(product)
    if max_pct <= 0:
        return False
    final_price = (price * (Decimal("1") - Decimal(str(max_pct)) / Decimal("100"))).quantize(Decimal("0.01"))
    return final_price <= budget


def _first_image_url(product: Product) -> str | None:
    images = list(getattr(product, "images", None) or [])
    if images and images[0].url:
        return images[0].url
    flat = getattr(product, "image_url", None)
    if isinstance(flat, str) and flat.strip():
        return flat.strip()
    return None


def _product_specs(product: Product) -> list[ProductSpecValue]:
    specs: list[ProductSpecValue] = []
    if product.vendor:
        specs.append(ProductSpecValue(name="vendor", value=product.vendor))
    if product.product_type:
        specs.append(ProductSpecValue(name="product_type", value=product.product_type))
    for option in product.options or []:
        for value in option.values or []:
            specs.append(ProductSpecValue(name=option.name, value=value))
    if product.tags:
        specs.append(ProductSpecValue(name="tags", value=", ".join(product.tags)))
    return specs


def _option_values(product: Product, name: str) -> set[str]:
    """Values clearly tied to the named attribute.

    Only option values and tags count — a generic variant title like
    "Standard" is never treated as an attribute value, so products are only
    excluded on provable contradiction.
    """
    values: set[str] = set()
    for option in product.options or []:
        if (option.name or "").strip().lower() == name:
            values |= {value.strip().lower() for value in (option.values or []) if value}
    values |= {tag.strip().lower() for tag in (product.tags or []) if tag}
    return values


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1}


def _taxonomy_match(phrase: str, value: str) -> bool:
    """Match a parsed category phrase against a store taxonomy value.

    Exact equality, then containment in either direction (handles
    pluralization like "laptops" vs "laptop" and suffixed names), then
    shared-token overlap. Matching is case-insensitive and conservative:
    values with no semantic relation to the phrase never match.
    """
    phrase_lower = phrase.lower().strip()
    value_lower = value.lower().strip()
    if not phrase_lower or not value_lower:
        return False
    if phrase_lower == value_lower:
        return True
    # Degenerate containment on tiny strings matches everything; require
    # both sides to be meaningful before trying it. Exact ids ("1") passed
    # above. Token overlap needs 2+ char tokens by construction.
    if len(phrase_lower) < 2 or len(value_lower) < 2:
        return False
    if phrase_lower in value_lower or value_lower in phrase_lower:
        return True
    return bool(_tokenize(phrase) & _tokenize(value))


def _candidate_text(candidate: ScoredProduct) -> str:
    parts = [candidate.title or "", candidate.description or ""]
    for spec in candidate.specs:
        parts.append(f"{spec.name} {spec.value}")
    return " ".join(parts)


def _category_match(candidate: ScoredProduct, intent: RecommendationIntent) -> float:
    category = (intent.product_type or "").lower()
    if not category:
        return 0.5
    haystack = _candidate_text(candidate).lower()
    if category in haystack:
        return 1.0
    category_tokens = _tokenize(category)
    haystack_tokens = _tokenize(haystack)
    if category_tokens and haystack_tokens:
        return len(category_tokens & haystack_tokens) / len(category_tokens)
    return 0.0


def _spec_match(candidate: ScoredProduct, intent: RecommendationIntent) -> float:
    specs = list(intent.required_specs or [])
    if intent.attributes:
        for name, value in intent.attributes.items():
            if value is not None and not any(spec.get("name") == name for spec in specs):
                specs.append({"name": str(name), "value": str(value)})
    if not specs:
        return 0.5
    text = _candidate_text(candidate).lower()
    matched = 0
    for spec in specs:
        name, value = _spec_name_value(spec)
        value_lower = str(value or "").lower()
        if not value_lower:
            matched += 1
            continue
        tokens = _tokenize(value_lower)
        if tokens and tokens <= _tokenize(text) or str(name).lower() in text and value_lower in text:
            matched += 1
    return matched / len(specs)


def _budget_fit(candidate: ScoredProduct, intent: RecommendationIntent) -> float:
    budget = intent.max_budget
    if budget is None:
        return 0.5
    if candidate.final_price is not None and candidate.final_price <= Decimal(str(budget)):
        return 1.0
    if candidate.discount_available:
        return 0.5
    if candidate.price <= Decimal(str(budget)):
        return 1.0
    return 0.0


def _use_case_match(candidate: ScoredProduct, intent: RecommendationIntent) -> float:
    use_case = (intent.use_case or "").lower()
    if not use_case:
        return 0.5
    text_tokens = _tokenize(_candidate_text(candidate))
    use_case_tokens = _tokenize(use_case)
    if use_case_tokens and text_tokens:
        return len(use_case_tokens & text_tokens) / len(use_case_tokens)
    return 0.0


def _brand_match(candidate: ScoredProduct, intent: RecommendationIntent) -> float:
    brand = (intent.brand or "").strip().lower()
    if not brand:
        return 0.5
    return 1.0 if brand in _candidate_text(candidate).lower() else 0.0


def _availability_score(candidate: ScoredProduct) -> float:
    if not candidate.in_stock:
        return 0.0
    return min(1.0, 0.5 + candidate.stock_quantity / 20.0)


def _build_match_reasons(
    candidate: ScoredProduct,
    intent: RecommendationIntent,
    category_score: float,
    spec_score: float,
    budget_score: float,
    use_case_score: float,
    brand_score: float,
) -> list[str]:
    reasons: list[str] = []
    if category_score > 0:
        reasons.append(f"Matches category '{intent.product_type}'")
    if spec_score >= 1.0:
        reasons.append("Meets all requested specs")
    elif spec_score > 0:
        reasons.append("Meets some requested specs")
    if budget_score >= 1.0:
        if candidate.discount_available:
            reasons.append(f"Fits budget after {candidate.discount_pct:g}% discount")
        else:
            reasons.append("Fits your budget")
    if use_case_score >= 1.0:
        reasons.append(f"Suitable for '{intent.use_case}'")
    elif use_case_score > 0:
        reasons.append("Partially matches your use case")
    if brand_score >= 1.0 and intent.brand:
        reasons.append(f"Matches preferred brand '{intent.brand}'")
    return reasons
