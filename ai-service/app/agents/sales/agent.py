import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.sales.nodes import (
    build_offer_node,
    close_sale_node,
    discover_needs_node,
    format_sales_response_node,
    handle_objection_node,
    recommend_products_node,
)
from app.agents.sales.state import SalesState
from app.application.recommendation.dto.sales_dto import SalesResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.application.recommendation.services import RecommendationService
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def route_after_discover(state: SalesState) -> str:
    if state.get("clarifying_question") or state.get("stage") == "discovery":
        return "format_response"
    return "recommend_products"


def route_after_recommend(state: SalesState) -> str:
    if not state.get("products"):
        return "format_response"
    return "handle_objection"


def route_after_objection(state: SalesState) -> str:
    return "build_offer"


def route_after_offer(state: SalesState) -> str:
    return "close_sale"


def route_after_close(state: SalesState) -> str:
    return "format_response"


class SalesAgent:
    """Conversational sales funnel: discovery -> qualification -> recommendation -> objection -> close."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        recommendation_service: RecommendationService,
        promo_service: PromoCodeService | None = None,
    ):
        self._llm = llm
        self._recommendation_service = recommendation_service
        self._promo_service = promo_service or PromoCodeService()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(SalesState)

        workflow.add_node("discover_needs", self._wrap(discover_needs_node))
        workflow.add_node("recommend_products", self._wrap(recommend_products_node))
        workflow.add_node("handle_objection", self._wrap(handle_objection_node))
        workflow.add_node("build_offer", self._wrap(build_offer_node))
        workflow.add_node("close_sale", self._wrap(close_sale_node))
        workflow.add_node("format_response", self._wrap(format_sales_response_node))

        workflow.set_entry_point("discover_needs")

        workflow.add_conditional_edges(
            "discover_needs",
            route_after_discover,
            {"recommend_products": "recommend_products", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "recommend_products",
            route_after_recommend,
            {"handle_objection": "handle_objection", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "handle_objection",
            route_after_objection,
            {"build_offer": "build_offer"},
        )
        workflow.add_conditional_edges(
            "build_offer",
            route_after_offer,
            {"close_sale": "close_sale"},
        )
        workflow.add_conditional_edges(
            "close_sale",
            route_after_close,
            {"format_response": "format_response"},
        )
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: SalesState) -> dict[str, Any]:
            extra = {}
            if node_fn in (discover_needs_node, handle_objection_node, build_offer_node):
                extra["llm"] = self._llm
            elif node_fn == recommend_products_node:
                extra["recommendation_service"] = self._recommendation_service
            elif node_fn == close_sale_node:
                extra["promo_service"] = self._promo_service
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        conversation_id: str | None = None,
        store_capabilities: dict[str, bool] | None = None,
        context: dict[str, Any] | None = None,
    ) -> SalesResponse:
        start = time.perf_counter()

        initial_state: SalesState = {
            "user_query": query,
            "store_id": store_id,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "history": history or [],
            "stage": "discovery",
            "customer_answers": {},
            "products": [],
            "offer": {},
            "objection": None,
            "promo_code": None,
            "checkout_note": None,
            "clarifying_question": None,
            "store_capabilities": store_capabilities or {},
            "context": context or {},
            "response": None,
            "error": None,
        }

        try:
            result = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("Sales agent failed: %s", exc, exc_info=True)
            return SalesResponse(
                query=query,
                store_id=store_id,
                customer_id=customer_id,
                rationale="I ran into an issue while preparing your recommendations. Please try again.",
            )

        response = result.get("response") or SalesResponse(query=query, store_id=store_id, customer_id=customer_id)
        response.latency_ms = (time.perf_counter() - start) * 1000
        return response
