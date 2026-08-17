import logging
from typing import Any

from app.agents.bundle.state import BundleState
from app.agents.bundle.tools import (
    build_bundle_response,
    build_compatible_pool,
    expand_use_case,
    find_candidates,
    get_or_create_promo,
    knapsack_bundles,
    merge_shopping_state,
    parse_budget,
    promo_capable,
    score_bundles,
)
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def parse_budget_node(state: BundleState, llm: BaseLLMProvider) -> dict[str, Any]:
    try:
        budget, desired_items, use_case = await parse_budget(state["user_query"], llm=llm)
        if not desired_items and use_case:
            desired_items = expand_use_case(use_case)
        items, budget, use_case = merge_shopping_state(
            state["user_query"],
            desired_items,
            budget,
            use_case,
            state.get("shopping_state"),
        )
        return {
            "budget": budget,
            "desired_items": items,
            "use_case": use_case,
            "budget_parsed": True,
            "error": None,
        }
    except Exception as exc:
        logger.error("Budget parsing failed: %s", exc, exc_info=True)
        return {
            "budget": None,
            "desired_items": [],
            "use_case": None,
            "budget_parsed": False,
            "error": f"Failed to parse budget: {exc}",
        }


async def find_candidates_node(
    state: BundleState,
    product_repo: ProductRepository,
) -> dict[str, Any]:
    if state.get("error") or not state.get("desired_items"):
        return {"candidates_by_type": {}}

    try:
        candidates = await find_candidates(
            desired_items=state["desired_items"],
            store_id=state["store_id"],
            product_repo=product_repo,
            category_names=state.get("category_names"),
        )
        return {"candidates_by_type": candidates}
    except Exception as exc:
        logger.error("Candidate search failed: %s", exc, exc_info=True)
        return {"candidates_by_type": {}, "error": f"Search failed: {exc}"}


async def compute_bundles_node(state: BundleState) -> dict[str, Any]:
    candidates = state.get("candidates_by_type", {})
    budget = state.get("budget")

    if not candidates:
        return {"bundles": []}

    try:
        pool = build_compatible_pool(candidates, state.get("category_names"))
        if not pool:
            return {"bundles": []}
        combinations = knapsack_bundles(
            pool,
            budget,
            category_names=state.get("category_names"),
        )
        scored = score_bundles(
            combinations,
            budget,
            pool,
            category_names=state.get("category_names"),
            requested_items=state["desired_items"],
        )
        return {"bundles": scored}
    except Exception as exc:
        logger.error("Bundle computation failed: %s", exc, exc_info=True)
        return {"bundles": [], "error": f"Bundle computation failed: {exc}"}


async def select_best_node(state: BundleState) -> dict[str, Any]:
    bundles = state.get("bundles", [])
    # B16: a bundle that does not fit the budget is never presented as a
    # valid selection. With no budget, everything is within budget.
    if state.get("budget") is not None:
        bundles = [b for b in bundles if b.within_budget]
    selected = bundles[:3] if bundles else []
    return {"selected": selected}


async def handle_promo_node(
    state: BundleState,
    promo_service: PromoCodeService,
) -> dict[str, Any]:
    capabilities = state.get("store_capabilities") or {}

    if not promo_capable(capabilities):
        logger.info("Store %s does not support promo codes; skipping promo generation.", state["store_id"])
        return {"promo_code": None, "promo_status": None}

    # B17: only the SINGLE selected bundle (rank 1) may receive a promo code.
    selected = state.get("selected", [])
    best = next((b for b in selected if b.rank == 1), None)
    if best is None or not best.products:
        return {"promo_code": None, "promo_status": None}

    try:
        code, status = await get_or_create_promo(
            best=best,
            store_id=state["store_id"],
            promo_service=promo_service,
        )
        if status == "invalid":
            best.promo_code = None
            best.promo_status = "invalid"
        elif code:
            best.promo_code = code
            best.promo_status = status
        return {"promo_code": code, "promo_status": status, "selected": selected}
    except Exception as exc:
        logger.error("Promo code generation failed: %s", exc, exc_info=True)
        return {"promo_code": None, "promo_status": None}


async def format_bundle_response_node(state: BundleState) -> dict[str, Any]:
    response = build_bundle_response(
        query=state.get("user_query", ""),
        store_id=state.get("store_id", ""),
        customer_id=state.get("customer_id"),
        budget=state.get("budget"),
        selected=state.get("selected", []),
        promo_code=state.get("promo_code"),
        promo_status=state.get("promo_status"),
    )
    return {"response": response}
