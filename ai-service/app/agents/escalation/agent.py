import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.escalation.nodes import (
    assign_team_node,
    determine_priority_node,
    format_escalation_response_node,
    notify_customer_node,
    notify_human_node,
    summarize_conversation_node,
)
from app.agents.escalation.state import EscalationState
from app.application.ticket.dto.escalation_dto import EscalationResponse
from app.application.ticket.services.notification_service import TicketNotificationService
from app.application.ticket.services.ticket_service import TicketService
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class EscalationAgent:
    """Hands off unresolved issues to a human: summarize, prioritize, assign, notify."""

    def __init__(
        self,
        llm: BaseLLMProvider | None = None,
        ticket_service: TicketService | None = None,
        notification_service: TicketNotificationService | None = None,
        customer_repo: ICustomerRepository | None = None,
    ):
        self._llm = llm
        self._ticket_service = ticket_service
        self._notification_service = notification_service
        self._customer_repo = customer_repo
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(EscalationState)

        workflow.add_node("summarize_conversation", self._wrap(summarize_conversation_node))
        workflow.add_node("determine_priority", self._wrap(determine_priority_node))
        workflow.add_node("assign_team", self._wrap(assign_team_node))
        workflow.add_node("notify_human", self._wrap(notify_human_node))
        workflow.add_node("notify_customer", self._wrap(notify_customer_node))
        workflow.add_node("format_response", self._wrap(format_escalation_response_node))

        workflow.set_entry_point("summarize_conversation")

        workflow.add_edge("summarize_conversation", "determine_priority")
        workflow.add_edge("determine_priority", "assign_team")
        workflow.add_edge("assign_team", "notify_human")
        workflow.add_edge("notify_human", "notify_customer")
        workflow.add_edge("notify_customer", "format_response")
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: EscalationState) -> dict[str, Any]:
            extra = {}
            if node_fn == summarize_conversation_node:
                extra["llm"] = self._llm
            elif node_fn == determine_priority_node:
                extra["customer_repo"] = self._customer_repo
            elif node_fn == notify_human_node:
                extra["ticket_service"] = self._ticket_service
            elif node_fn == notify_customer_node:
                extra["notification_service"] = self._notification_service
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        query: str,
        store_id: str,
        customer_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        conversation_id: str | None = None,
        context: dict[str, Any] | None = None,  # noqa: ARG002 - uniform sub-agent runner contract
        original_agent: str | None = None,
        reason: str | None = None,
        ticket_id: str | None = None,
        category: str | None = None,
    ) -> EscalationResponse:
        start = time.perf_counter()

        initial_state: EscalationState = {
            "user_query": query,
            "store_id": store_id,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "history": history or [],
            "original_agent": original_agent,
            "reason": reason,
            "ticket_id": ticket_id,
            "category": category,
            "tier": None,
            "priority": None,
            "assigned_to": None,
            "eta": None,
            "summary": None,
            "notification_message": None,
            "response": None,
            "error": None,
        }

        try:
            result = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error("Escalation agent failed: %s", exc, exc_info=True)
            return EscalationResponse(
                query=query,
                store_id=store_id,
                customer_id=customer_id,
                error=f"Escalation agent failed: {exc}",
            )

        response = result.get("response") or EscalationResponse(query=query, store_id=store_id, customer_id=customer_id)
        response.latency_ms = (time.perf_counter() - start) * 1000
        return response
