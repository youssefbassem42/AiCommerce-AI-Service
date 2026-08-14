import json
import logging
from decimal import Decimal
from typing import Any

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
    DiscountInfo,
)
from app.application.recommendation.promo_service import PromoCodeService
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


def _get_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider("openai")


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
        model="gpt-4o-mini",
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


async def find_candidates(
    desired_items: list[str],
    store_id: str,
    product_repo: ProductRepository,
) -> dict[str, list[Product]]:
    if not desired_items:
        return {}

    candidates_by_type: dict[str, list[Product]] = {}

    for item in desired_items:
        products = await product_repo.find_many(
            {"store_id": store_id, "product_type": {"$regex": item, "$options": "i"}},
            limit=50,
        )
        if not products:
            products = await product_repo.find_many(
                {"store_id": store_id, "title": {"$regex": item, "$options": "i"}},
                limit=50,
            )
        in_stock = [p for p in products if any(v.inventory_quantity > 0 for v in p.variants)]
        if in_stock:
            candidates_by_type[item] = in_stock[:20]

    return candidates_by_type


def _min_price(product: Product) -> Decimal:
    prices = [v.price.amount for v in product.variants if v.inventory_quantity > 0]
    return min(prices) if prices else Decimal("Inf")


def _discounted_price(product: Product) -> Decimal:
    """Lowest in-stock price after the product's maximum allowed discount (Fix 5.4)."""
    price = _min_price(product)
    if price == Decimal("Inf"):
        return price
    discount_pct = float(product.metadata.get("max_discount_pct", 0.0) or 0.0)
    return price * (Decimal("1") - Decimal(str(discount_pct)) / Decimal("100"))


def knapsack_bundles(
    candidates_by_type: dict[str, list[Product]],
    budget: float | None,
) -> list[list[Product]]:
    """Enumerate bundle combinations of 1-3 items (Fix 5.2-5.4).

    ``budget=None`` means "no budget constraint": every in-stock product is a
    candidate and all 1-3 item combinations are returned (bounded by
    ``_UNLIMITED_MODE_TOP_PRODUCTS`` and ``_MAX_BUNDLES``).
    With a budget, a product is eligible when it can fit individually —
    at the normal price or after its maximum allowed discount — and a
    combination is kept when its discounted total fits. The discount-fit
    decision itself stays in ``score_bundles``.
    """
    all_products: list[Product] = []
    for products in candidates_by_type.values():
        all_products.extend(products)

    unique = list({p.id: p for p in all_products}.values())
    unique.sort(key=lambda p: _min_price(p))

    if budget is None:
        eligible = unique[:_UNLIMITED_MODE_TOP_PRODUCTS]
    else:
        budget_dec = Decimal(str(budget))
        eligible = [p for p in unique if _discounted_price(p) <= budget_dec]

    bundles: list[list[Product]] = []
    for i, p1 in enumerate(eligible):
        if budget is None or _discounted_price(p1) <= Decimal(str(budget)):
            bundles.append([p1])

        for p2 in eligible[i + 1 :]:
            if budget is not None and _discounted_price(p1) + _discounted_price(p2) > Decimal(str(budget)):
                continue
            bundles.append([p1, p2])

            for p3 in eligible[i + 2 :]:
                if budget is not None:
                    discounted_total = _discounted_price(p1) + _discounted_price(p2) + _discounted_price(p3)
                    if discounted_total > Decimal(str(budget)):
                        continue
                bundles.append([p1, p2, p3])
                if len(bundles) >= _MAX_BUNDLES:
                    return bundles
            if len(bundles) >= _MAX_BUNDLES:
                return bundles

    return bundles


def score_bundles(
    bundles: list[list[Product]],
    budget: float | None,
    candidates_by_type: dict[str, list[Product]],
) -> list[BundleCandidate]:
    """Price bundles against the budget (Fix 5.3-5.4).

    - No budget (Fix 5.2): normal prices, everything is within budget.
    - ``total <= budget`` (Fix 5.3): normal price, no discount applied.
    - ``total > budget`` (Fix 5.4): apply each product's maximum allowed
      discount; the bundle is within budget only if the discounted total fits.
    """
    budget_dec = Decimal(str(budget)) if budget is not None else None
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

        scored.append(
            BundleCandidate(
                products=discount_infos,
                total_original=total_original,
                total_discount=total_discount,
                total_after_discount=total_after,
                remaining_budget=max(0.0, remaining),
                within_budget=within_budget,
            )
        )

    scored.sort(
        key=lambda b: (
            not b.within_budget,  # within-budget bundles first
            -float(b.total_discount),  # higher discount first (desc)
            float(b.total_after_discount),  # lower total after discount
            -float(b.total_original),  # higher original value first
        )
    )

    return scored[:5]


async def get_or_create_promo(
    selected: list[BundleCandidate],
    product_ids: list[str],
    store_id: str,
    promo_service: PromoCodeService,
) -> tuple[str | None, list[BundleCandidate]]:
    """Create a real coupon on the e-commerce platform (Fix 5.5).

    A promo code is only requested when the best bundle actually needs a
    discount (Fix 5.3: bundles that fit at normal price get no code). If the
    platform cannot create a coupon, ``generate_code`` returns None and no
    code is shown to the customer.
    """
    if not selected:
        return None, selected

    best = selected[0]
    if best.total_original <= 0 or best.total_discount <= 0:
        return None, selected

    total_discount_pct = float(best.total_discount / best.total_original * 100)

    code = await promo_service.generate_code(
        store_id=store_id,
        product_ids=product_ids,
        discount_pct=round(total_discount_pct, 2),
    )

    updated = list(selected)
    if updated and code:
        updated[0].promo_code = code

    return code, updated


def build_bundle_response(
    query: str,
    store_id: str,
    customer_id: str | None,
    budget: float | None,
    selected: list[BundleCandidate],
    promo_code: str | None,
) -> BundleResponse:
    if selected and selected[0].products:
        total_count = len(selected)
        if budget and budget > 0:
            budget_str = f"${budget:.2f}"
            rationale = (
                f"Found {total_count} bundle option(s) within {budget_str}. "
                f"Best bundle saves ${float(selected[0].total_discount):.2f} "
                f"with {len(selected[0].products)} item(s)."
            )
        else:
            rationale = (
                f"Found {total_count} bundle option(s). "
                f"Best bundle is ${float(selected[0].total_after_discount):.2f} "
                f"with {len(selected[0].products)} item(s)."
            )
        if promo_code:
            rationale += f" Use promo code {promo_code} to get this discount."
    else:
        if budget and budget > 0:
            rationale = (
                f"No bundles found within ${budget:.2f}. Try increasing your budget or choosing different products."
            )
        else:
            rationale = "No bundles found. Try choosing different products."

    return BundleResponse(
        query=query,
        store_id=store_id,
        customer_id=customer_id,
        budget=budget or 0.0,
        bundles=selected,
        promo_code=promo_code,
        rationale=rationale,
    )
