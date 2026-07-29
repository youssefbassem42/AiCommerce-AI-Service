import logging
from typing import Any

from app.agents.recommendation.state import RecommendationState
from app.agents.recommendation.tools import (
    apply_budget_filter,
    build_product_cards,
    filter_inventory,
    parse_intent,
    search_spec_vectors,
)
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def parse_intent_node(state: RecommendationState, llm: BaseLLMProvider) -> dict[str, Any]:
    try:
        intent = await parse_intent(state["user_query"], llm=llm)
        return {"intent": intent, "error": None}
    except Exception as exc:
        logger.error("Intent parsing failed: %s", exc, exc_info=True)
        return {"intent": None, "error": f"Failed to parse intent: {exc}"}


async def search_candidates_node(
    state: RecommendationState,
    retriever_service: RetrieverService,
) -> dict[str, Any]:
    if state.get("error"):
        return {"candidates": []}

    intent = state.get("intent")
    if intent is None:
        return {"candidates": []}

    try:
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
        within_budget = await apply_budget_filter(
            in_stock,
            state.get("intent.max_budget") if state.get("intent") else None,
            product_repo,
        )
        return {"filtered": within_budget}
    except Exception as exc:
        logger.error("Inventory filtering failed: %s", exc, exc_info=True)
        return {"filtered": candidates}


async def format_response_node(state: RecommendationState) -> dict[str, Any]:
    filtered = state.get("filtered", [])
    query = state.get("user_query", "")
    store_id = state.get("store_id", "")
    customer_id = state.get("customer_id")

    product_cards = build_product_cards(filtered[:10])

    total_count = len(product_cards)
    if product_cards:
        rationale = f"Found {total_count} product(s) matching your request. Top pick: {product_cards[0].title}."
    else:
        rationale = "No products matched your criteria. Try adjusting your requirements or browsing our full catalog."

    response = RecommendationResponse(
        query=query,
        store_id=store_id,
        customer_id=customer_id,
        products=product_cards,
        rationale=rationale,
        total_count=total_count,
    )

    return {"response": response}
