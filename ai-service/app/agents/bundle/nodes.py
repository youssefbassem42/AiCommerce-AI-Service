import logging
from typing import Any, Dict, List

from app.agents.bundle.state import BundleState
from app.agents.bundle.tools import (
    build_bundle_response,
    find_candidates,
    get_or_create_promo,
    knapsack_bundles,
    parse_budget,
    score_bundles,
)
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def parse_budget_node(state: BundleState, llm: BaseLLMProvider) -> Dict[str, Any]:
    try:
        budget, desired_items = await parse_budget(state["user_query"], llm=llm)
        return {
            "budget": budget,
            "desired_items": desired_items,
            "budget_parsed": True,
            "error": None,
        }
    except Exception as exc:
        logger.error("Budget parsing failed: %s", exc, exc_info=True)
        return {
            "budget": None,
            "desired_items": [],
            "budget_parsed": False,
            "error": f"Failed to parse budget: {exc}",
        }


async def find_candidates_node(
    state: BundleState,
    product_repo: ProductRepository,
) -> Dict[str, Any]:
    if state.get("error") or not state.get("desired_items"):
        return {"candidates_by_type": {}}

    try:
        candidates = await find_candidates(
            desired_items=state["desired_items"],
            store_id=state["store_id"],
            product_repo=product_repo,
        )
        return {"candidates_by_type": candidates}
    except Exception as exc:
        logger.error("Candidate search failed: %s", exc, exc_info=True)
        return {"candidates_by_type": {}, "error": f"Search failed: {exc}"}


async def compute_bundles_node(state: BundleState) -> Dict[str, Any]:
    candidates = state.get("candidates_by_type", {})
    budget = state.get("budget")

    if not candidates or budget is None or budget <= 0:
        return {"bundles": []}

    try:
        combinations = knapsack_bundles(candidates, budget)
        scored = score_bundles(combinations, budget, candidates)
        return {"bundles": scored}
    except Exception as exc:
        logger.error("Bundle computation failed: %s", exc, exc_info=True)
        return {"bundles": [], "error": f"Bundle computation failed: {exc}"}


async def select_best_node(state: BundleState) -> Dict[str, Any]:
    bundles = state.get("bundles", [])
    selected = bundles[:3] if bundles else []
    return {"selected": selected}


async def handle_promo_node(
    state: BundleState,
    promo_service: PromoCodeService,
) -> Dict[str, Any]:
    capabilities = state.get("store_capabilities") or {}

    if not capabilities.get("has_promo_codes", True):
        logger.info("Store %s does not support promo codes; skipping promo generation.", state["store_id"])
        return {"promo_code": None}

    selected = state.get("selected", [])
    if not selected:
        return {"promo_code": None}

    product_ids: List[str] = []
    for bundle in selected:
        for p in bundle.products:
            if p.product_id not in product_ids:
                product_ids.append(p.product_id)

    if not product_ids:
        return {"promo_code": None}

    try:
        code, updated = await get_or_create_promo(
            selected=selected,
            product_ids=product_ids,
            store_id=state["store_id"],
            promo_service=promo_service,
        )
        return {"promo_code": code, "selected": updated}
    except Exception as exc:
        logger.error("Promo code generation failed: %s", exc, exc_info=True)
        return {"promo_code": None}


async def format_bundle_response_node(state: BundleState) -> Dict[str, Any]:
    budget = state.get("budget") or 0.0
    response = build_bundle_response(
        query=state.get("user_query", ""),
        store_id=state.get("store_id", ""),
        customer_id=state.get("customer_id"),
        budget=budget,
        selected=state.get("selected", []),
        promo_code=state.get("promo_code"),
    )
    return {"response": response}
