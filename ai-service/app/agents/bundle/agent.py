import logging
import time
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph

from app.agents.bundle.nodes import (
    compute_bundles_node,
    find_candidates_node,
    format_bundle_response_node,
    handle_promo_node,
    parse_budget_node,
    select_best_node,
)
from app.agents.bundle.state import BundleState
from app.application.recommendation.dto.recommendation_dto import BundleResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.repositories import ProductRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def route_after_budget(state: BundleState) -> str:
    if state.get("error") or not state.get("desired_items"):
        return "format_response"
    return "find_candidates"


def route_after_candidates(state: BundleState) -> str:
    if not state.get("candidates_by_type"):
        return "format_response"
    return "compute_bundles"


def route_after_bundles(state: BundleState) -> str:
    if not state.get("bundles"):
        return "format_response"
    return "select_best"


def route_after_select(state: BundleState) -> str:
    capabilities = state.get("store_capabilities") or {}
    if capabilities.get("has_promo_codes", False):
        return "handle_promo"
    return "format_response"


def route_after_promo(state: BundleState) -> str:
    return "format_response"


class BundleSuggestionAgent:
    def __init__(
        self,
        product_repo: ProductRepository,
        llm: BaseLLMProvider,
        promo_service: Optional[PromoCodeService] = None,
    ):
        self._product_repo = product_repo
        self._llm = llm
        self._promo_service = promo_service or PromoCodeService()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(BundleState)

        workflow.add_node("parse_budget", self._wrap(parse_budget_node))
        workflow.add_node("find_candidates", self._wrap(find_candidates_node))
        workflow.add_node("compute_bundles", self._wrap(compute_bundles_node))
        workflow.add_node("select_best", self._wrap(select_best_node))
        workflow.add_node("handle_promo", self._wrap(handle_promo_node))
        workflow.add_node("format_response", self._wrap(format_bundle_response_node))

        workflow.set_entry_point("parse_budget")

        workflow.add_conditional_edges(
            "parse_budget",
            route_after_budget,
            {"find_candidates": "find_candidates", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "find_candidates",
            route_after_candidates,
            {"compute_bundles": "compute_bundles", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "compute_bundles",
            route_after_bundles,
            {"select_best": "select_best", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "select_best",
            route_after_select,
            {"handle_promo": "handle_promo", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "handle_promo",
            route_after_promo,
            {"format_response": "format_response"},
        )
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: BundleState) -> Dict[str, Any]:
            extra = {}
            if node_fn == parse_budget_node:
                extra["llm"] = self._llm
            elif node_fn == find_candidates_node:
                extra["product_repo"] = self._product_repo
            elif node_fn == handle_promo_node:
                extra["promo_service"] = self._promo_service
            return await node_fn(state, **extra)
        return wrapped

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: Optional[str] = None,
        store_capabilities: Optional[Dict[str, bool]] = None,
    ) -> BundleResponse:
        start = time.perf_counter()

        initial_state: BundleState = {
            "user_query": query,
            "store_id": store_id,
            "customer_id": customer_id,
            "budget": None,
            "desired_items": [],
            "budget_parsed": False,
            "candidates_by_type": {},
            "bundles": [],
            "selected": [],
            "promo_code": None,
            "response": None,
            "error": None,
            "store_capabilities": store_capabilities or {},
        }

        result = await self._graph.ainvoke(initial_state)

        latency = (time.perf_counter() - start) * 1000
        response = result.get("response")
        if response:
            response.latency_ms = latency

        return response or BundleResponse(
            query=query,
            store_id=store_id,
            customer_id=customer_id,
            rationale="Unable to generate bundle suggestions at this time.",
        )
