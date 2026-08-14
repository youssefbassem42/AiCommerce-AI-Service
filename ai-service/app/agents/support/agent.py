import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.escalation.agent import EscalationAgent
from app.agents.support.nodes import (
    categorize_issue_node,
    collect_feedback_node,
    escalate_if_needed_node,
    generate_response_node,
    handle_refund_node,
    resolve_order_issue_node,
    retrieve_facts_node,
    verify_customer_node,
)
from app.agents.support.state import SupportState
from app.application.ticket.dto.support_dto import SupportResponse
from app.application.ticket.services.ticket_service import TicketService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.commerce.repositories.product_repository import ProductRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

ORDER_CATEGORIES = {"order_status", "returns", "refund"}


def route_after_verify(state: SupportState) -> str:
    return "categorize_issue"


def route_after_categorize(state: SupportState) -> str:
    if state.get("issue_category") in ORDER_CATEGORIES:
        return "resolve_order_issue"
    return "retrieve_facts"


def route_after_order(state: SupportState) -> str:
    if state.get("issue_category") == "refund":
        return "handle_refund"
    return "retrieve_facts"


def route_after_refund(state: SupportState) -> str:
    return "escalate_if_needed"


def route_after_escalate(state: SupportState) -> str:
    return "collect_feedback"


def route_after_feedback(state: SupportState) -> str:
    return "generate_response"


class SupportAgent:
    """Conversational, store-aware support agent: verify, categorize, retrieve facts, resolve, escalate, respond."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        customer_repo: ICustomerRepository | None = None,
        order_repo: OrderRepository | None = None,
        ticket_service: TicketService | None = None,
        escalation_agent: EscalationAgent | None = None,
        retriever_service: Any | None = None,
        product_repo: ProductRepository | None = None,
    ):
        self._llm = llm
        self._customer_repo = customer_repo
        self._order_repo = order_repo
        self._ticket_service = ticket_service
        self._escalation_agent = escalation_agent
        self._retriever_service = retriever_service
        self._product_repo = product_repo
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(SupportState)

        workflow.add_node("verify_customer", self._wrap(verify_customer_node))
        workflow.add_node("categorize_issue", self._wrap(categorize_issue_node))
        workflow.add_node("retrieve_facts", self._wrap(retrieve_facts_node))
        workflow.add_node("resolve_order_issue", self._wrap(resolve_order_issue_node))
        workflow.add_node("handle_refund", self._wrap(handle_refund_node))
        workflow.add_node("escalate_if_needed", self._wrap(escalate_if_needed_node))
        workflow.add_node("collect_feedback", self._wrap(collect_feedback_node))
        workflow.add_node("generate_response", self._wrap(generate_response_node))

        workflow.set_entry_point("verify_customer")

        workflow.add_conditional_edges(
            "verify_customer",
            route_after_verify,
            {"categorize_issue": "categorize_issue"},
        )
        workflow.add_conditional_edges(
            "categorize_issue",
            route_after_categorize,
            {"resolve_order_issue": "resolve_order_issue", "retrieve_facts": "retrieve_facts"},
        )
        workflow.add_conditional_edges(
            "resolve_order_issue",
            route_after_order,
            {"handle_refund": "handle_refund", "retrieve_facts": "retrieve_facts"},
        )
        workflow.add_edge("retrieve_facts", "escalate_if_needed")
        workflow.add_conditional_edges(
            "handle_refund",
            route_after_refund,
            {"escalate_if_needed": "escalate_if_needed"},
        )
        workflow.add_conditional_edges(
            "escalate_if_needed",
            route_after_escalate,
            {"collect_feedback": "collect_feedback"},
        )
        workflow.add_conditional_edges(
            "collect_feedback",
            route_after_feedback,
            {"generate_response": "generate_response"},
        )
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: SupportState) -> dict[str, Any]:
            extra = {}
            if node_fn == verify_customer_node:
                extra["customer_repo"] = self._customer_repo
            elif node_fn == categorize_issue_node:
                extra["llm"] = self._llm
            elif node_fn == retrieve_facts_node:
                extra["llm"] = self._llm
                extra["retriever_service"] = self._retriever_service
                extra["product_repo"] = self._product_repo
            elif node_fn == resolve_order_issue_node:
                extra["order_repo"] = self._order_repo
            elif node_fn == escalate_if_needed_node:
                extra["escalation_agent"] = self._escalation_agent
                extra["ticket_service"] = self._ticket_service
            elif node_fn == generate_response_node:
                extra["llm"] = self._llm
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        conversation_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> SupportResponse:
        start = time.perf_counter()
        context = context or {}

        initial_state: SupportState = {
            "user_query": query,
            "store_id": store_id,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "history": history or [],
            "verified": False,
            "customer": None,
            "issue_category": None,
            "order": None,
            "order_matches": [],
            "resolution_steps": [],
            "refund_info": None,
            "escalation_needed": False,
            "escalation_reason": None,
            "ticket_id": None,
            "priority": None,
            "assigned_to": None,
            "eta": None,
            "satisfaction_question": None,
            "response": None,
            "error": None,
            "context": context,
            "memory": context.get("memory") or {},
            "customer_profile": context.get("customer"),
        }

        try:
            result = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("Support agent failed: %s", exc, exc_info=True)
            return SupportResponse(
                query=query,
                store_id=store_id,
                customer_id=customer_id,
                rationale="I ran into an issue while looking into this. Please try again.",
            )

        response = result.get("response") or SupportResponse(query=query, store_id=store_id, customer_id=customer_id)
        response.latency_ms = (time.perf_counter() - start) * 1000
        return response
