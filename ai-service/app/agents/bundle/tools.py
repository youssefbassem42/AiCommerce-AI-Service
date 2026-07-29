import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

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
Extract structured information from a user's request about what they want to buy within a budget.

User query: {query}

Return a JSON object with these fields:
- budget: the maximum amount they want to spend as a number (float). If they say "$300", return 300.0. If no budget is mentioned, return null.
- desired_items: list of product categories or types they want (e.g., ["monitor"], ["monitor", "keyboard", "mouse"]).
  If the query says "and" or lists multiple items, include all of them.
- use_case: how they will use the items, or null if unclear.

Only return valid JSON. No markdown, no explanation."""


def _get_llm() -> BaseLLMProvider:
    return LLMProviderFactory().get_provider("openai")


async def parse_budget(
    query: str,
    llm: Optional[BaseLLMProvider] = None,
) -> Tuple[Optional[float], List[str]]:
    provider = llm or _get_llm()
    request = ChatRequest(
        messages=[
            MessageDTO(role="system", content="You extract budget and shopping intent from user queries. Return only valid JSON."),
            MessageDTO(role="user", content=BUDGET_PARSE_PROMPT.format(query=query)),
        ],
        model="gpt-4o-mini",
        json_mode=True,
    )
    response = await provider.structured_output(request, Dict[str, Any])
    data = json.loads(response.message.content)
    budget = data.get("budget")
    desired_items = data.get("desired_items", [])
    return budget, desired_items


async def find_candidates(
    desired_items: List[str],
    store_id: str,
    product_repo: ProductRepository,
) -> Dict[str, List[Product]]:
    if not desired_items:
        return {}

    candidates_by_type: Dict[str, List[Product]] = {}

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
        in_stock = [
            p for p in products
            if any(v.inventory_quantity > 0 for v in p.variants)
        ]
        if in_stock:
            candidates_by_type[item] = in_stock[:20]

    return candidates_by_type


def _min_price(product: Product) -> Decimal:
    prices = [v.price.amount for v in product.variants if v.inventory_quantity > 0]
    return min(prices) if prices else Decimal("Inf")


def knapsack_bundles(
    candidates_by_type: Dict[str, List[Product]],
    budget: float,
) -> List[List[Product]]:
    all_products: List[Product] = []
    for products in candidates_by_type.values():
        all_products.extend(products)

    unique = list({p.id: p for p in all_products}.values())
    unique.sort(key=lambda p: _min_price(p))

    affordable = [p for p in unique if _min_price(p) <= Decimal(str(budget))]
    bundles: List[List[Product]] = []

    for i, p1 in enumerate(affordable):
        price1 = _min_price(p1)
        if price1 <= Decimal(str(budget)):
            bundles.append([p1])

        for p2 in affordable[i + 1:]:
            price2 = _min_price(p2)
            if price1 + price2 <= Decimal(str(budget)):
                bundles.append([p1, p2])

            for p3 in affordable[i + 2:]:
                price3 = _min_price(p3)
                total = price1 + price2 + price3
                if total <= Decimal(str(budget)):
                    bundles.append([p1, p2, p3])
                else:
                    break

    return bundles


def score_bundles(
    bundles: List[List[Product]],
    budget: float,
    candidates_by_type: Dict[str, List[Product]],
) -> List[BundleCandidate]:
    scored: List[BundleCandidate] = []

    for bundle in bundles:
        total_original = Decimal("0")
        discount_infos: List[DiscountInfo] = []

        for product in bundle:
            price = _min_price(product)
            if price == Decimal("Inf"):
                continue

            discount_pct = float(product.metadata.get("max_discount_pct", 0.0) or 0.0)
            discount_amount = price * Decimal(str(discount_pct / 100))

            discount_infos.append(DiscountInfo(
                product_id=product.id,
                product_title=product.title,
                original_price=price,
                discount_pct=discount_pct,
                discount_amount=discount_amount,
                price_after_discount=price - discount_amount,
            ))
            total_original += price

        if not discount_infos:
            continue

        total_discount = sum(d.discount_amount for d in discount_infos)
        total_after = total_original - total_discount
        remaining = float(budget) - float(total_after)

        scored.append(BundleCandidate(
            products=discount_infos,
            total_original=total_original,
            total_discount=total_discount,
            total_after_discount=total_after,
            remaining_budget=max(0.0, remaining),
            within_budget=remaining >= 0,
        ))

    scored.sort(key=lambda b: (
        float(b.total_discount),  # higher discount first (desc)
        -b.remaining_budget,  # lower remaining budget is better (asc)
    ))
    scored.sort(key=lambda b: b.remaining_budget / budget if budget > 0 else 1.0)

    return scored[:5]


async def get_or_create_promo(
    selected: List[BundleCandidate],
    product_ids: List[str],
    store_id: str,
    promo_service: PromoCodeService,
) -> Tuple[Optional[str], List[BundleCandidate]]:
    if not selected:
        return None, selected

    best = selected[0]
    total_discount_pct = float(
        best.total_discount / best.total_original * 100
        if best.total_original > 0 else 0
    )

    code = await promo_service.generate_code(
        store_id=store_id,
        product_ids=product_ids,
        discount_pct=round(total_discount_pct, 2),
    )

    updated = list(selected)
    if updated:
        updated[0].promo_code = code

    return code, updated


def build_bundle_response(
    query: str,
    store_id: str,
    customer_id: Optional[str],
    budget: float,
    selected: List[BundleCandidate],
    promo_code: Optional[str],
) -> BundleResponse:

    total_count = len(selected)

    if selected and selected[0].products:
        budget_str = f"${budget:.2f}" if budget and budget > 0 else "your budget"
        rationale = (
            f"Found {total_count} bundle option(s) within {budget_str}. "
            f"Best bundle saves ${float(selected[0].total_discount):.2f} "
            f"with {len(selected[0].products)} item(s)."
        )
        if promo_code:
            rationale += f" Use promo code {promo_code} to get this discount."
    else:
        budget_str = f"${budget:.2f}" if budget and budget > 0 else "your budget"
        rationale = (
            f"No bundles found within {budget_str}. "
            "Try increasing your budget or choosing different products."
        )

    return BundleResponse(
        query=query,
        store_id=store_id,
        customer_id=customer_id,
        budget=budget,
        bundles=selected,
        promo_code=promo_code,
        rationale=rationale,
    )
