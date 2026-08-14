import logging
from typing import Any

from app.agents.recommendation.state import RecommendationState
from app.agents.recommendation.tools import (
    apply_budget_filter,
    build_product_cards,
    explain_recommendation,
    filter_inventory,
    parse_intent,
    search_spec_vectors,
)
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.catalog_service import RecommendationCatalogService
from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    RecommendationResponse,
)
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def parse_intent_node(state: RecommendationState, llm: BaseLLMProvider) -> dict[str, Any]:
    try:
        intent = await parse_intent(
            state["user_query"],
            llm=llm,
            shopping_state=state.get("shopping_state"),
        )
        clarifying_question = _missing_requirement_question(intent, state.get("shopping_state"))
        return {
            "intent": intent,
            "clarifying_question": clarifying_question,
            "error": None,
        }
    except Exception as exc:
        logger.error("Intent parsing failed: %s", exc, exc_info=True)
        return {"intent": None, "error": f"Failed to parse intent: {exc}"}


def _missing_requirement_question(
    intent: RecommendationIntent,
    shopping_state: dict[str, Any] | None,
) -> str | None:
    """Ask for the first unanswered requirement so the search has full constraints.

    Priority: what to buy -> budget -> use case. Returns None when the intent
    is complete enough to search.
    """
    if not intent:
        return "What kind of product are you looking for?"

    missing: list[str] = []
    if not intent.product_type:
        missing.append("category")
    if intent.max_budget is None:
        missing.append("budget")
    if not intent.use_case:
        missing.append("use_case")

    if not missing:
        return None

    next_question = missing[0]
    questions = {
        "category": "What kind of product are you looking for?",
        "budget": "What's your budget?",
        "use_case": "What will you use it for?",
    }
    return questions[next_question]


async def search_candidates_node(
    state: RecommendationState,
    retriever_service: RetrieverService,
    product_repo: ProductRepository,
) -> dict[str, Any]:
    if state.get("error"):
        return {"candidates": []}

    intent = state.get("intent")
    if intent is None:
        return {"candidates": []}

    try:
        # Deterministic retrieval first (Fix 4.2): catalog -> hard filters ->
        # candidates. The catalog record is authoritative, so candidates are
        # already resolved (price_resolved=True).
        products = await RecommendationCatalogService.retrieve_candidates(
            intent=intent,
            store_id=state["store_id"],
            product_repo=product_repo,
        )
        if products:
            candidates = RecommendationCatalogService.build_scored_candidates(products)
            return {"candidates": candidates}

        # Fuzzy fallback: vector search only when the catalog could not
        # satisfy the hard constraints deterministically.
        candidates = await search_spec_vectors(
            intent=intent,
            retriever_service=retriever_service,
            store_id=state["store_id"],
        )
        return {"candidates": candidates}
    except Exception as exc:
        logger.error("Candidate search failed: %s", exc, exc_info=True)
        return {"candidates": [], "error": f"Search failed: {exc}"}


async def filter_inventory_node(
    state: RecommendationState,
    product_repo: ProductRepository,
) -> dict[str, Any]:
    candidates = state.get("candidates", [])
    if not candidates:
        return {"filtered": []}

    try:
        in_stock = await filter_inventory(candidates, product_repo)
        intent = state.get("intent")
        max_budget = intent.max_budget if intent is not None else None
        within_budget = await apply_budget_filter(
            in_stock,
            max_budget,
            product_repo,
        )
        with_discounts = RecommendationCatalogService.apply_discount_strategy(within_budget, max_budget)
        return {"filtered": with_discounts}
    except Exception as exc:
        logger.error("Inventory filtering failed: %s", exc, exc_info=True)
        return {"filtered": candidates}


async def rank_candidates_node(state: RecommendationState) -> dict[str, Any]:
    """Deterministic ranking (Fix 4.3)."""
    filtered = state.get("filtered", [])
    if not filtered:
        return {"ranked": []}
    intent = state.get("intent")
    if intent is None:
        return {"ranked": filtered}
    ranked = RecommendationCatalogService.rank_candidates(filtered, intent)
    return {"ranked": ranked}


async def format_response_node(
    state: RecommendationState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    ranked = state.get("ranked", [])
    query = state.get("user_query", "")
    store_id = state.get("store_id", "")
    customer_id = state.get("customer_id")
    clarifying_question = state.get("clarifying_question")
    intent = state.get("intent")

    product_cards = build_product_cards(ranked[:10])

    total_count = len(product_cards)
    top = ranked[0] if ranked else None
    budget = intent.max_budget if intent is not None else None
    discount_available = bool(top and top.discount_available)
    discount = top.discount_pct if top else 0.0
    final_price = float(top.final_price) if top and top.final_price is not None else None

    if clarifying_question:
        rationale = clarifying_question
    elif product_cards:
        structured = {
            "type": "recommendation",
            "products": [
                {
                    "product_id": card.product_id,
                    "title": card.title,
                    "price": str(card.price),
                    "currency": card.currency,
                    "final_price": str(card.final_price) if card.final_price is not None else None,
                    "discount_pct": card.discount_pct,
                    "match_reasons": card.match_reasons,
                }
                for card in product_cards
            ],
            "budget": budget,
            "discount_available": discount_available,
            "discount": discount,
            "final_price": final_price,
        }
        explanation = await explain_recommendation(structured, llm=llm)
        rationale = explanation or (
            f"Found {total_count} product(s) matching your request. Top pick: {product_cards[0].title}."
        )
    else:
        rationale = "No products matched your criteria. Try adjusting your requirements or browsing our full catalog."

    response = RecommendationResponse(
        type="recommendation",
        query=query,
        store_id=store_id,
        customer_id=customer_id,
        products=product_cards,
        rationale=rationale,
        total_count=total_count,
        clarifying_question=clarifying_question,
        budget=budget,
        discount_available=discount_available,
        discount=discount,
        final_price=final_price,
    )

    return {"response": response}
