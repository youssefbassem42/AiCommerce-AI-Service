import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.recommendation.nodes import (
    filter_inventory_node,
    format_response_node,
    parse_intent_node,
    rank_candidates_node,
    search_candidates_node,
)
from app.agents.recommendation.state import RecommendationState
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def route_after_intent(state: RecommendationState) -> str:
    if state.get("error") or state.get("intent") is None or state.get("clarifying_question"):
        return "format_response"
    return "search_candidates"


def route_after_search(state: RecommendationState) -> str:
    if not state.get("candidates"):
        return "format_response"
    return "filter_inventory"


def route_after_filter(state: RecommendationState) -> str:
    if not state.get("filtered"):
        return "format_response"
    return "rank_candidates"


def route_after_rank(state: RecommendationState) -> str:
    return "format_response"


class RecommendationAgent:
    def __init__(
        self,
        retriever_service: RetrieverService,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
    ):
        self._retriever_service = retriever_service
        self._product_repo = product_repo
        self._llm = llm
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(RecommendationState)

        workflow.add_node("parse_intent", self._wrap(parse_intent_node))
        workflow.add_node("search_candidates", self._wrap(search_candidates_node))
        workflow.add_node("filter_inventory", self._wrap(filter_inventory_node))
        workflow.add_node("rank_candidates", self._wrap(rank_candidates_node))
        workflow.add_node("format_response", self._wrap(format_response_node))

        workflow.set_entry_point("parse_intent")

        workflow.add_conditional_edges(
            "parse_intent",
            route_after_intent,
            {"search_candidates": "search_candidates", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "search_candidates",
            route_after_search,
            {"filter_inventory": "filter_inventory", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "filter_inventory",
            route_after_filter,
            {"rank_candidates": "rank_candidates", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "rank_candidates",
            route_after_rank,
            {"format_response": "format_response"},
        )
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: RecommendationState) -> dict[str, Any]:
            extra = {}
            if node_fn == parse_intent_node:
                extra["llm"] = self._llm
            elif node_fn == search_candidates_node:
                extra["retriever_service"] = self._retriever_service
                extra["product_repo"] = self._product_repo
            elif node_fn == filter_inventory_node:
                extra["product_repo"] = self._product_repo
            elif node_fn == format_response_node:
                extra["llm"] = self._llm
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        shopping_state: dict[str, Any] | None = None,
    ) -> RecommendationResponse:
        start = time.perf_counter()

        initial_state: RecommendationState = {
            "user_query": query,
            "store_id": store_id,
            "customer_id": customer_id,
            "shopping_state": shopping_state,
            "intent": None,
            "candidates": [],
            "filtered": [],
            "ranked": [],
            "clarifying_question": None,
            "response": None,
            "error": None,
        }

        result = await self._graph.ainvoke(initial_state)

        latency = (time.perf_counter() - start) * 1000
        response = result.get("response")
        if response:
            response.latency_ms = latency

        return response or RecommendationResponse(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            rationale="Unable to generate recommendations at this time.",
        )
