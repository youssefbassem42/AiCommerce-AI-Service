import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.coordinator.nodes import (
    SubAgentRunner,
    classify_intent_node,
    execute_sub_agent_node,
    extract_context_node,
    format_response_node,
    handle_fallback_node,
    route_to_agent_node,
)
from app.agents.coordinator.state import CoordinatorState
from app.domain.conversation.repositories.conversation_repository import ConversationRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

EXECUTABLE_INTENTS = {"bundle", "recommendation"}
DEFERRED_INTENTS = {"general"}
FALLBACK_INTENTS = {"sales", "support", "marketing", "analytics", "escalation", "integration"}


def route_after_classify(state: CoordinatorState) -> str:
    if state.get("error") or not state.get("intent"):
        return "handle_fallback"
    return "route_to_agent"


def route_after_route(state: CoordinatorState) -> str:
    sub_agent = state.get("sub_agent")
    if sub_agent in EXECUTABLE_INTENTS:
        return "execute_sub_agent"
    if sub_agent in DEFERRED_INTENTS:
        return "format_response"
    return "handle_fallback"


class CoordinatorAgent:
    """Routes user requests to the right sub-agent with intent classification."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        conversation_repo: ConversationRepository | None = None,
        sub_agents: dict[str, SubAgentRunner] | None = None,
    ):
        self._llm = llm
        self._conversation_repo = conversation_repo
        self._sub_agents = sub_agents or {}
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(CoordinatorState)

        workflow.add_node("extract_context", self._wrap(extract_context_node))
        workflow.add_node("classify_intent", self._wrap(classify_intent_node))
        workflow.add_node("route_to_agent", self._wrap(route_to_agent_node))
        workflow.add_node("execute_sub_agent", self._wrap(execute_sub_agent_node))
        workflow.add_node("handle_fallback", self._wrap(handle_fallback_node))
        workflow.add_node("format_response", self._wrap(format_response_node))

        workflow.set_entry_point("extract_context")
        workflow.add_edge("extract_context", "classify_intent")

        workflow.add_conditional_edges(
            "classify_intent",
            route_after_classify,
            {"route_to_agent": "route_to_agent", "handle_fallback": "handle_fallback"},
        )
        workflow.add_conditional_edges(
            "route_to_agent",
            route_after_route,
            {
                "execute_sub_agent": "execute_sub_agent",
                "handle_fallback": "handle_fallback",
                "format_response": "format_response",
            },
        )
        workflow.add_edge("execute_sub_agent", "format_response")
        workflow.add_edge("handle_fallback", "format_response")
        workflow.add_edge("format_response", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: CoordinatorState) -> dict[str, Any]:
            extra = {}
            if node_fn in (classify_intent_node, extract_context_node, handle_fallback_node):
                extra["llm"] = self._llm
            if node_fn == extract_context_node:
                extra["conversation_repo"] = self._conversation_repo
            if node_fn == execute_sub_agent_node:
                extra["sub_agents"] = self._sub_agents
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        user_input: str,
        store_id: str,
        conversation_id: str | None = None,
        customer_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> CoordinatorState:
        start = time.perf_counter()

        initial_state: CoordinatorState = {
            "user_input": user_input,
            "intent": None,
            "confidence": None,
            "sub_agent": None,
            "conversation_id": conversation_id,
            "store_id": store_id,
            "customer_id": customer_id,
            "context": context or {},
            "response": None,
            "needs_clarification": False,
            "error": None,
        }

        result = await self._graph.ainvoke(initial_state)

        response = result.get("response") or {}
        response["latency_ms"] = (time.perf_counter() - start) * 1000
        result["response"] = response

        return result
