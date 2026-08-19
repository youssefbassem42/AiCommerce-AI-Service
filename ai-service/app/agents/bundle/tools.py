import json
import logging
from collections import Counter
from decimal import Decimal
from typing import Any

from app.application.commerce.complementarity import build_rules
from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
    DiscountInfo,
)
from app.application.recommendation.promo_service import PromoCodeService, PromoValidationResult
from app.core.ai_settings import ai_settings
from app.domain.commerce.aggregates.product import Product
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

BUDGET_PARSE_PROMPT = """You are a budget and shopping intent parser.
Extract structured information from a user's request about what they want to buy.

User query: {query}

Return a JSON object with these fields:
- budget: the maximum amount they want to spend as a number (float). If they say "$300", return 300.0. If no budget is mentioned, return null.
- desired_items: list of product categories or types they want (e.g., ["monitor"], ["monitor", "keyboard", "mouse"]).
  A query with "and", "+", or a comma-separated list mentions MULTIPLE items — include ALL of them
  (e.g., "mouse and keyboard" -> ["mouse", "keyboard"], "laptop + mouse" -> ["laptop", "mouse"]).
  If a product type is named twice (e.g. "two controllers"), list it twice.
  A bare category like "a gaming setup" or "home office setup" names NO concrete products:
  leave desired_items as [] and set use_case instead.
- use_case: how they will use the items (e.g., "gaming", "home office", "office work"), or null if unclear.
  For "gaming setup" / "home office setup" style queries, use_case must be set.

Only return valid JSON. No markdown, no explanation."""

# Deterministic use-case -> default category expansion (Fix 5.1). The LLM never
# decides what belongs in a setup; this mapping does, so results are stable.
USE_CASE_CATEGORIES: dict[str, list[str]] = {
    "gaming": ["keyboard", "mouse", "headset", "monitor", "controller", "speakers"],
    "home office": ["monitor", "keyboard", "mouse", "chair", "desk", "lamp"],
    "office": ["monitor", "keyboard", "mouse", "chair", "desk"],
    "work from home": ["monitor", "keyboard", "mouse", "chair", "desk"],
    "study": ["laptop", "monitor", "keyboard", "mouse", "desk"],
    "streaming": ["microphone", "webcam", "headset", "monitor", "keyboard"],
}

# Max bundle combinations returned per type bucket, keeps the search bounded
# when no budget constrains the combination space (Fix 5.2).
_UNLIMITED_MODE_TOP_PRODUCTS = 15
_MAX_BUNDLES = 400
# Deterministic cap on compatible additions per bucket before combination
# generation (B16: bounded candidate space, no 400+ meaningless combos).
_TOP_COMPATIBLE_PER_BUCKET = 10

# Words signalling the shopper is REPLACING the previous intent rather than
# adding to it. Used to merge Domain 4 shopping state with the current message
# without a second classifier (B16 multi-turn).
_REPLACEMENT_SIGNALS = ("actually", "instead", "change", "switch", "make it a", "not the", "forget", "never mind")


# Single source of truth for promo capability (B17): the Agent routing and the
# promo node must never disagree. Default is FALSE everywhere.
def promo_capable(capabilities: dict[str, bool] | None) -> bool:
    return bool((capabilities or {}).get("has_promo_codes", False))


def expand_use_case(use_case: str | None) -> list[str]:
    """Map a setup use case onto default product categories (Fix 5.1).

    Returns [] when the use case is unknown, so the caller can fall back to
    clarifying instead of guessing.
    """
    if not use_case:
        return []
    normalized = use_case.strip().lower()
    for key, categories in USE_CASE_CATEGORIES.items():
        if key in normalized:
            return list(categories)
    return []


def merge_shopping_state(
    query: str,
    parsed_items: list[str],
    parsed_budget: float | None,
    parsed_use_case: str | None,
    shopping_state: dict[str, Any] | None,
) -> tuple[list[str], float | None, str | None]:
    """Merge the Domain 4 shopping state with the parsed current message.

    - The current message wins over stale state (B16).
    - An additive message ("add the accessories") keeps the state category as
      the primary and treats the parsed items as complements.
    - A replacement message ("actually, make it a camera") replaces the primary.
    """
    state = shopping_state or {}
    state_category = state.get("category") or state.get("product_type")
    lowered = (query or "").lower()
    is_replacement = any(signal in lowered for signal in _REPLACEMENT_SIGNALS)

    items: list[str]
    if parsed_items:
        if (
            state_category
            and not is_replacement
            and str(state_category).lower() not in [i.lower() for i in parsed_items]
        ):
            items = [str(state_category)] + list(parsed_items)
        else:
            items = list(parsed_items)
    elif state_category:
        items = [str(state_category)]
    else:
        items = []

    budget = parsed_budget if parsed_budget is not None else state.get("budget")
    use_case = parsed_use_case or state.get("use_case")
    return items, budget, use_case


def _get_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider(ai_settings.DEFAULT_PROVIDER)


async def parse_budget(
    query: str,
    llm: BaseLLMProvider | None = None,
) -> tuple[float | None, list[str], str | None]:
    provider = llm or _get_llm()
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content="You extract budget and shopping intent from user queries. Return only valid JSON.",
            ),
            MessageDTO(role="user", content=BUDGET_PARSE_PROMPT.format(query=query)),
        ],
        model=ai_settings.DEFAULT_MODEL,
        json_mode=True,
    )
    response = await provider.structured_output(request, dict[str, Any])
    data = json.loads(response.message.content)
    budget = data.get("budget")
    if isinstance(budget, str):
        budget = float(budget.strip().replace("$", "").replace(",", "")) if budget.strip() else None
    elif budget is not None:
        budget = float(budget)
    desired_items = [str(item).strip() for item in data.get("desired_items", []) if str(item).strip()]
    use_case = data.get("use_case")
    return budget, desired_items, use_case


def is_active(product: Product) -> bool:
    return getattr(product, "status", "") == "active" and getattr(product, "deleted_at", None) is None


def is_available(product: Product) -> bool:
    """True when the product is active and has any sellable inventory.

    Variants are authoritative when present; flat-schema products (synced
    stores) use ``price`` + ``inventory_quantity``.
    """
    if not is_active(product):
        return False
    variants = getattr(product, "variants", None)
    if variants:
        return any(v.inventory_quantity > 0 for v in variants)
    return int(getattr(product, "inventory_quantity", 0) or 0) > 0


async def find_candidates(
    desired_items: list[str],
    store_id: str,
    product_repo: ProductRepository,
    category_names: dict[str, str] | None = None,
) -> dict[str, list[Product]]:
    """Discover in-stock, active candidates per requested item (store-scoped).

    Search order: product_type -> title -> category name (when known). Only
    active products with at least one in-stock variant (or flat-schema stock)
    qualify — inventory is a hard constraint (B16).
    """
    if not desired_items:
        return {}

    candidates_by_type: dict[str, list[Product]] = {}
    category_names = dict(category_names or {})

    for item in desired_items:
        products = await _search_item(item, store_id, product_repo, category_names)
        in_stock = [p for p in products if is_available(p)]
        if in_stock:
            candidates_by_type[item] = in_stock[:20]

    return candidates_by_type


async def _search_item(
    item: str,
    store_id: str,
    product_repo: ProductRepository,
    category_names: dict[str, str],
) -> list[Product]:
    """One requested item -> active candidates (product_type, then title, then category)."""
    products = await product_repo.find_many(
        {"store_id": store_id, "product_type": {"$regex": item, "$options": "i"}},
        limit=50,
    )
    if products:
        return [p for p in products if is_active(p)]

    products = await product_repo.find_many(
        {"store_id": store_id, "title": {"$regex": item, "$options": "i"}},
        limit=50,
    )
    if products:
        return [p for p in products if is_active(p)]

    # Category-name fallback: some catalogs carry no product_type/title match
    # but the store's own taxonomy names the category (B16 uses real data).
    category_ids = [cid for cid, name in category_names.items() if item.lower() in name.lower()]
    if category_ids:
        products = await product_repo.find_many(
            {"store_id": store_id, "category_id": {"$in": category_ids}},
            limit=50,
        )
        return [p for p in products if is_active(p)]
    return []


def _min_price(product: Product) -> Decimal:
    variants = getattr(product, "variants", None)
    if variants:
        prices = [v.price.amount for v in variants if v.inventory_quantity > 0]
        if prices:
            return min(prices)
        return Decimal("Inf")
    price = getattr(product, "price", None)
    return price.amount if price is not None else Decimal("Inf")


def _discounted_price(product: Product) -> Decimal:
    """Lowest in-stock price after the product's maximum allowed discount (Fix 5.4)."""
    price = _min_price(product)
    if price == Decimal("Inf"):
        return price
    discount_pct = float(product.metadata.get("max_discount_pct", 0.0) or 0.0)
    return price * (Decimal("1") - Decimal(str(discount_pct)) / Decimal("100"))


def requested_counts(desired_items: list[str]) -> Counter[str]:
    return Counter(item.lower() for item in desired_items)


def build_compatible_pool_relaxed(
    candidates_by_type: dict[str, list[Product]],
    category_names: dict[str, str] | None = None,
) -> dict[str, list[Product]]:
    """Like ``build_compatible_pool`` but keeps zero-complementarity buckets.

    Stores whose catalog has no rule matches (e.g. synced catalogs without
    product_type/category metadata) lose every secondary bucket to the
    complementarity filter, collapsing suggestions to single products even
    when in-stock pairs exist. When the strict pool ends up with only the
    primary bucket, the remaining buckets are kept (deterministically capped)
    so cross-type pairs are still considered; the scoring layer demotes
    unrelated pairs, so rank 1 still prefers meaningful bundles.
    """
    pool = build_compatible_pool(candidates_by_type, category_names)
    if len(pool) > 1 or not candidates_by_type:
        return pool
    types = list(candidates_by_type)
    for item in types[1:]:
        if item not in pool:
            bucket = list(candidates_by_type[item])
            bucket.sort(key=lambda c: str(getattr(c, "id", "") or ""))
            pool[item] = bucket[:_TOP_COMPATIBLE_PER_BUCKET]
    return pool


def build_compatible_pool(
    candidates_by_type: dict[str, list[Product]],
    category_names: dict[str, str] | None = None,
) -> dict[str, list[Product]]:
    """Reduce the candidate space to the primary type + genuinely compatible types.

    B16: no arbitrary 1-3 enumeration across every type. The primary type is
    the first requested item; other buckets keep only products compatible with
    at least one primary product, deterministically capped. Same-type pairs
    remain possible but always score below complementary bundles (the coverage
    component is the only signal that rewards a twice-requested type).
    """
    if not candidates_by_type:
        return {}
    types = list(candidates_by_type)
    primary_type = types[0]
    rules = build_rules(category_names)
    primary_products = candidates_by_type[primary_type]

    pool: dict[str, list[Product]] = {primary_type: primary_products[:_TOP_COMPATIBLE_PER_BUCKET]}
    for item in types[1:]:
        compatible: list[Product] = []
        for candidate in candidates_by_type[item]:
            if any(rules.pair_complementarity(p, candidate).score > 0 for p in primary_products):
                compatible.append(candidate)
        if compatible:
            compatible.sort(key=lambda c: str(getattr(c, "id", "") or ""))
            pool[item] = compatible[:_TOP_COMPATIBLE_PER_BUCKET]
    return pool


def knapsack_bundles(
    candidates_by_type: dict[str, list[Product]],
    budget: float | None,
    category_names: dict[str, str] | None = None,
) -> list[list[Product]]:
    """Enumerate bundle combinations of 1-3 items (Fix 5.2-5.4).

    ``budget=None`` means "no budget constraint": every in-stock product is a
    candidate and all 1-3 item combinations are returned (bounded by
    ``_UNLIMITED_MODE_TOP_PRODUCTS`` and ``_MAX_BUNDLES``).
    With a budget, a product is eligible when it can fit individually —
    at the normal price or after its maximum allowed discount — and a
    combination is kept when its discounted total fits. The discount-fit
    decision itself stays in ``score_bundles``.

    B16: same-category pairs are never eliminated here — the complementarity
    score demotes them below meaningful bundles, and the requested-coverage
    component rewards a type requested twice ("two controllers").
    """
    category_names = dict(category_names or {})
    all_products: list[Product] = []
    for products in candidates_by_type.values():
        all_products.extend(products)

    unique = list({p.id: p for p in all_products}.values())
    unique.sort(key=lambda p: _min_price(p))

    if budget is None:
        eligible = unique[:_UNLIMITED_MODE_TOP_PRODUCTS]
        budget_dec: Decimal | None = None
    else:
        budget_dec = Decimal(str(budget))
        eligible = [p for p in unique if _discounted_price(p) <= budget_dec]

    bundles: list[list[Product]] = []
    for i, p1 in enumerate(eligible):
        bundles.append([p1])
        if len(bundles) >= _MAX_BUNDLES:
            return bundles

        for j in range(i + 1, len(eligible)):
            p2 = eligible[j]
            if budget_dec is not None and _discounted_price(p1) + _discounted_price(p2) > budget_dec:
                continue
            bundles.append([p1, p2])
            if len(bundles) >= _MAX_BUNDLES:
                return bundles

            for k in range(j + 1, len(eligible)):
                p3 = eligible[k]
                if budget_dec is not None:
                    discounted_total = _discounted_price(p1) + _discounted_price(p2) + _discounted_price(p3)
                    if discounted_total > budget_dec:
                        continue
                bundles.append([p1, p2, p3])
                if len(bundles) >= _MAX_BUNDLES:
                    return bundles

    return bundles


def _bundle_coverage(bundle: list[Product], candidates_by_type: dict[str, list[Product]]) -> float:
    """Fraction of requested types covered by the bundle (deterministic)."""
    if not candidates_by_type:
        return 0.0
    bucket_ids: dict[str, set[str]] = {}
    for item, products in candidates_by_type.items():
        bucket_ids[item] = {p.id for p in products}
    bundle_ids = {p.id for p in bundle}
    covered = sum(1 for bucket in bucket_ids.values() if bucket & bundle_ids)
    return covered / len(bucket_ids)


def _requested_coverage(
    bundle: list[Product],
    requested_items: list[str],
    candidates_by_type: dict[str, list[Product]],
) -> float:
    """Coverage against the shopper's explicit requests, counting repetitions.

    "two controllers" -> ["console", "controller", "controller"]: a bundle with
    two controllers covers 3/3 requests; one controller covers 2/3. This is the
    only signal that lets a duplicated request rank as the primary intent.
    """
    if not requested_items or not candidates_by_type:
        return _bundle_coverage(bundle, candidates_by_type)
    used: Counter[str] = Counter()
    covered = 0
    for item in requested_items:
        bucket = candidates_by_type.get(item)
        if bucket is None:
            continue
        bucket_ids = {p.id for p in bucket}
        claimed = used[item]
        total_in_bucket = sum(1 for p in bundle if p.id in bucket_ids)
        if claimed < total_in_bucket:
            covered += 1
            used[item] += 1
    return covered / len(requested_items)


def score_bundles_relaxed(
    bundles: list[list[Product]],
    budget: float | None,
    candidates_by_type: dict[str, list[Product]],
    category_names: dict[str, str] | None = None,
    requested_items: list[str] | None = None,
) -> list[BundleCandidate]:
    """Like ``score_bundles`` but a pair covering more requested types outranks a single.

    The single-product baseline (0.5) lets one product beat an unrelated pair
    (single 0.625 > pair 0.5 at zero complementarity), which surfaces as
    "only one product suggested" for stores without rule matches. Re-rank:
    within-budget candidates sort by requested-coverage first (then the
    original score order), so a multi-item bundle that covers the shopper's
    types wins while meaningful bundles keep their relative order.
    """
    scored = score_bundles(
        bundles,
        budget,
        candidates_by_type,
        category_names=category_names,
        requested_items=requested_items,
    )
    if len(scored) < 2:
        return scored
    ranked = sorted(
        scored,
        key=lambda b: (
            not b.within_budget,
            -float(b.relevance_score),
            -float(b.compatibility_score),
            -float(b.score),
            float(b.total_after_discount),
            len(b.products),
            "|".join(sorted(p.product_id for p in b.products)),
        ),
    )
    for index, candidate in enumerate(ranked):
        candidate.rank = index + 1
    return ranked


def score_bundles(
    bundles: list[list[Product]],
    budget: float | None,
    candidates_by_type: dict[str, list[Product]],
    category_names: dict[str, str] | None = None,
    requested_items: list[str] | None = None,
) -> list[BundleCandidate]:
    """Price, complementarity-score, rank and sort bundles deterministically.

    - No budget (Fix 5.2): normal prices, everything is within budget.
    - ``total <= budget`` (Fix 5.3): normal price, no discount applied.
    - ``total > budget`` (Fix 5.4): apply each product's maximum allowed
      discount; the bundle is within budget only if the discounted total fits.

    B16/B17: every candidate is scored for complementarity, then ranked
    (``rank`` 1-based) with a deterministic sort:
        within_budget -> score -> relevance -> cheaper -> fewer items -> stable ids.
    Complementarity dominates discount: an irrelevant deal never outranks a
    meaningful bundle.
    """
    budget_dec = Decimal(str(budget)) if budget is not None else None
    rules = build_rules(category_names)
    scored: list[BundleCandidate] = []

    for bundle in bundles:
        total_original = Decimal("0")
        discount_infos: list[DiscountInfo] = []

        for product in bundle:
            price = _min_price(product)
            if price == Decimal("Inf"):
                continue

            discount_pct = float(product.metadata.get("max_discount_pct", 0.0) or 0.0)
            product_images = list(product.images or [])
            product_url = getattr(product, "handle", None) or None
            image_url = product_images[0].url if product_images and product_images[0].url else None

            discount_infos.append(
                DiscountInfo(
                    product_id=product.id,
                    product_title=product.title,
                    original_price=price,
                    discount_pct=discount_pct,
                    discount_amount=Decimal("0"),
                    price_after_discount=price,
                    product_url=product_url,
                    image_url=image_url,
                )
            )
            total_original += price

        if not discount_infos:
            continue

        if budget_dec is None or total_original <= budget_dec:
            # Normal price (Fix 5.2/5.3): discounts stay at 0.
            within_budget = True
            total_after = total_original
            remaining = 0.0 if budget_dec is None else float(budget_dec - total_original)
            for info in discount_infos:
                info.discount_pct = 0.0
        else:
            # Fix 5.4: maximum allowed discount, then check the budget again.
            total_discount = Decimal("0")
            for info in discount_infos:
                discount_amount = info.original_price * Decimal(str(info.discount_pct / 100))
                info.discount_amount = discount_amount
                info.price_after_discount = info.original_price - discount_amount
                total_discount += discount_amount
            total_after = total_original - total_discount
            within_budget = total_after <= budget_dec
            remaining = float(budget_dec - total_after) if within_budget else 0.0

        total_discount = total_original - total_after

        complementarity = rules.bundle_complementarity(bundle)
        labels = rules.bundle_labels(bundle)
        coverage = _requested_coverage(bundle, requested_items or [], candidates_by_type)
        score = 0.6 * complementarity + 0.35 * coverage + (0.15 if within_budget else 0.0)

        scored.append(
            BundleCandidate(
                products=discount_infos,
                total_original=total_original,
                total_discount=total_discount,
                total_after_discount=total_after,
                remaining_budget=max(0.0, remaining),
                within_budget=within_budget,
                compatibility_score=round(complementarity, 4),
                relevance_score=round(coverage, 4),
                score=round(score, 4),
                complementarity_labels=labels,
            )
        )

    scored.sort(
        key=lambda b: (
            not b.within_budget,  # within-budget bundles first
            -float(b.score),  # complementarity-dominant score (B16/B17)
            -float(b.relevance_score),
            float(b.total_after_discount),  # cheaper first (tie-break)
            len(b.products),  # fewer items (tie-break)
            "|".join(sorted(p.product_id for p in b.products)),  # stable ids
        )
    )

    for index, candidate in enumerate(scored):
        candidate.rank = index + 1

    return scored[:5]


async def get_or_create_promo(
    best: BundleCandidate,
    store_id: str,
    promo_service: PromoCodeService,
) -> tuple[str | None, str | None]:
    """Create a real coupon for the SINGLE selected bundle (B17), then validate
    it against the real bundle subtotal (L4).

    Returns ``(code, promo_status)`` where ``promo_status`` is one of
    ``validated`` | ``unverified`` | ``invalid`` | ``None``. A code is never
    returned when the platform refused to create it, and a code the checkout
    rejects is dropped. An unverifiable code is kept but marked ``unverified``
    (never claimed as verified).
    """
    if best is None or best.total_original <= 0:
        return None, None

    # A promo code only exists when the selected bundle is genuinely
    # discounted: a bundle that fits the budget at normal price needs no
    # coupon (legacy contract, Fix 5.3).
    if best.total_discount <= 0:
        return None, None

    product_ids = [p.product_id for p in best.products]
    if not product_ids:
        return None, None

    total_discount_pct = float(best.total_discount / best.total_original * 100)
    code = await promo_service.generate_code(
        store_id=store_id,
        product_ids=product_ids,
        discount_pct=round(total_discount_pct, 2),
    )
    if not code:
        return None, None

    try:
        validation = await promo_service.validate_code(
            store_id=store_id,
            code=code,
            subtotal=best.total_original,
        )
    except Exception as exc:
        logger.warning("Promo validation failed for store %s: %s", store_id, exc)
        validation = PromoValidationResult(status="unavailable", reason="validation failed")

    if validation.status == "invalid":
        logger.info(
            "Promo %s for store %s rejected by checkout (%s); dropping it.",
            code,
            store_id,
            validation.reason,
        )
        return None, "invalid"

    status = "validated" if validation.status == "valid" else "unverified"
    return code, status


def build_bundle_response(
    query: str,
    store_id: str,
    customer_id: str | None,
    budget: float | None,
    selected: list[BundleCandidate],
    promo_code: str | None,
    promo_status: str | None = None,
) -> BundleResponse:
    if selected and selected[0].products:
        total_count = len(selected)
        best = selected[0]
        if budget and budget > 0:
            budget_str = f"${budget:.2f}"
            rationale = (
                f"Found {total_count} bundle option(s) within {budget_str}. "
                f"Best bundle saves ${float(best.total_discount):.2f} "
                f"with {len(best.products)} item(s)."
            )
        else:
            rationale = (
                f"Found {total_count} bundle option(s). "
                f"Best bundle is ${float(best.total_after_discount):.2f} "
                f"with {len(best.products)} item(s)."
            )
        if promo_code:
            if promo_status == "validated":
                rationale += f" Use promo code {promo_code} at checkout to get this discount."
            else:
                rationale += (
                    f" I've created promo code {promo_code} for this bundle — "
                    "apply it at checkout to claim the discount."
                )
    else:
        if budget and budget > 0:
            rationale = (
                f"No bundles found within ${budget:.2f}. Try increasing your budget or choosing different products."
            )
        elif selected is not None and not selected:
            rationale = "No bundles found. Try choosing different products or tell me what you'd like to buy together."
        else:
            rationale = "No bundles found. Try choosing different products."

    return BundleResponse(
        query=query,
        store_id=store_id,
        customer_id=customer_id,
        budget=budget or 0.0,
        bundles=selected,
        promo_code=promo_code,
        promo_status=promo_status,
        rationale=rationale,
    )
