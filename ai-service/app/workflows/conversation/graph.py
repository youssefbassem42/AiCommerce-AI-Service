"""Conversation Workflow: orchestrates the coordinator, sub-agents, and memory agents."""

import logging
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.coordinator.agent import CoordinatorAgent
from app.agents.coordinator.nodes import SubAgentRunner
from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.core.ai_settings import ai_settings
from app.infrastructure.providers.base import BaseLLMProvider
from app.workflows.conversation.state import ConversationWorkflowState

logger = logging.getLogger(__name__)

EXECUTABLE_INTENTS = {"bundle", "recommendation"}
DEFAULT_MAX_TURNS = 4
DEFAULT_CONTEXT_WINDOW = 20


class ConversationWorkflow:
    """High-level conversational loop around the CoordinatorAgent, sub-agents, and MemoryAgent."""

    def __init__(
        self,
        coordinator: CoordinatorAgent,
        llm: BaseLLMProvider,
        sub_agents: dict[str, SubAgentRunner] | None = None,
        memory_agent: Any | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
    ):
        self._coordinator = coordinator
        self._llm = llm
        self._sub_agents = sub_agents or {}
        self._memory_agent = memory_agent
        self._max_turns = max_turns
        self._context_window = context_window
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(ConversationWorkflowState)

        workflow.add_node("validate_input", self._wrap(validate_input_node))
        workflow.add_node("route_to_agent", self._wrap(route_to_agent_node))
        workflow.add_node("execute_agent", self._wrap(execute_agent_node))
        workflow.add_node("format_response", self._wrap(format_response_node))
        workflow.add_node("update_memory", self._wrap(update_memory_node))
        workflow.add_node("check_continuation", self._wrap(check_continuation_node))

        workflow.set_entry_point("validate_input")
        workflow.add_conditional_edges(
            "validate_input",
            lambda state: "route_to_agent" if not state.get("error") else "format_response",
            {"route_to_agent": "route_to_agent", "format_response": "format_response"},
        )
        workflow.add_conditional_edges(
            "route_to_agent",
            route_after_route,
            {
                "execute_agent": "execute_agent",
                "format_response": "format_response",
            },
        )
        workflow.add_edge("execute_agent", "format_response")
        workflow.add_edge("format_response", "update_memory")
        workflow.add_edge("update_memory", "check_continuation")
        workflow.add_edge("check_continuation", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: ConversationWorkflowState) -> dict[str, Any]:
            extra: dict[str, Any] = {}
            if node_fn == route_to_agent_node:
                extra["coordinator"] = self._coordinator
            elif node_fn == execute_agent_node:
                extra["llm"] = self._llm
                extra["sub_agents"] = self._sub_agents
            elif node_fn == update_memory_node:
                extra["memory_agent"] = self._memory_agent
            return await node_fn(state, **extra)

        return wrapped

    async def run(
        self,
        user_input: str,
        store_id: str,
        customer_id: str | None = None,
        conversation_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        initial_state: ConversationWorkflowState = {
            "user_input": user_input,
            "messages": history or [],
            "current_turn": 1,
            "max_turns": self._max_turns,
            "context_window": self._context_window,
            "metadata": metadata or {},
            "agent_trace": [],
            "store_id": store_id,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "response": None,
            "error": None,
        }

        result = await self._graph.ainvoke(initial_state)
        response = result.get("response") or {}

        return ChatResponse(
            id=str(uuid.uuid4()),
            model=ai_settings.DEFAULT_MODEL,
            provider="orchestration",
            message=MessageDTO(
                role="assistant",
                content=response.get("content", ""),
            ),
            usage=UsageDTO(),
            latency_ms=response.get("latency_ms", 0.0),
            metadata={
                "intent": response.get("intent"),
                "sub_agent": response.get("sub_agent"),
                "needs_clarification": response.get("needs_clarification", False),
                "trace": result.get("agent_trace", []),
            },
        )


def route_after_route(state: ConversationWorkflowState) -> str:
    response = state.get("response") or {}
    intent = response.get("intent")
    if intent == "general" and response.get("content") is None:
        return "execute_agent"
    return "format_response"


async def validate_input_node(
    state: ConversationWorkflowState,
) -> dict[str, Any]:
    user_input = (state.get("user_input") or "").strip()
    if not user_input:
        return {
            "error": "user_input is required",
            "response": {"content": "Please provide a message so I can help you.", "needs_clarification": False},
        }

    current_turn = state.get("current_turn", 1)
    if current_turn > state.get("max_turns", DEFAULT_MAX_TURNS):
        return {
            "error": "max_turns_exceeded",
            "response": {
                "content": "This conversation has reached its turn limit. Please start a new one.",
                "needs_clarification": False,
            },
        }

    messages = list(state.get("messages") or [])
    messages.append({"role": "user", "content": user_input})
    return {"messages": messages}


async def route_to_agent_node(
    state: ConversationWorkflowState,
    coordinator: CoordinatorAgent,
) -> dict[str, Any]:
    messages = state.get("messages") or []
    context_window = state.get("context_window", DEFAULT_CONTEXT_WINDOW)
    recent = messages[-context_window:]

    coordinator_result = await coordinator.run(
        user_input=state["user_input"],
        store_id=state.get("store_id") or "",
        conversation_id=state.get("conversation_id"),
        customer_id=state.get("customer_id"),
        context={"history": recent},
    )

    response = coordinator_result.get("response") or {}
    intent = coordinator_result.get("intent") or "general"
    response["intent"] = intent
    response["sub_agent"] = coordinator_result.get("sub_agent")

    trace = list(state.get("agent_trace") or [])
    trace.append(
        {
            "step": "coordinator",
            "intent": intent,
            "confidence": coordinator_result.get("confidence"),
            "sub_agent": coordinator_result.get("sub_agent"),
            "needs_clarification": coordinator_result.get("needs_clarification", False),
        }
    )
    return {"response": response, "agent_trace": trace}


async def execute_agent_node(
    state: ConversationWorkflowState,
    llm: BaseLLMProvider,
    sub_agents: dict[str, SubAgentRunner],
) -> dict[str, Any]:
    response = dict(state.get("response") or {})
    if response.get("content") is not None:
        return {"response": response}

    intent = response.get("intent")
    messages = state.get("messages") or []
    store_id = state.get("store_id") or ""
    customer_id = state.get("customer_id")

    try:
        if intent in EXECUTABLE_INTENTS:
            runner = sub_agents.get(intent)
            if not runner:
                response["content"] = (
                    "I'm sorry, the assistant for this request isn't available right now. Please try again in a moment."
                )
            else:
                result = await runner(
                    query=state["user_input"],
                    store_id=store_id,
                    customer_id=customer_id,
                )
                rationale = getattr(result, "rationale", None)
                response["content"] = rationale or str(result)
                response["data"] = getattr(result, "model_dump", lambda: {})() if hasattr(result, "model_dump") else {}
        else:
            request = ChatRequest(
                messages=[
                    MessageDTO(role="system", content="You are a helpful e-commerce assistant."),
                    *[MessageDTO(role=m.get("role", "user"), content=m.get("content", "")) for m in messages],
                ],
                model=ai_settings.DEFAULT_MODEL,
            )
            reply = await llm.chat(request)
            response["content"] = reply.message.content
    except Exception:
        logger.exception("execute_agent failed")
        response["content"] = "I ran into an issue while answering. Please try again."

    trace = list(state.get("agent_trace") or [])
    trace.append({"step": "execute_agent", "intent": intent})
    return {"response": response, "agent_trace": trace}


async def format_response_node(
    state: ConversationWorkflowState,
) -> dict[str, Any]:
    response = dict(state.get("response") or {})
    if state.get("error") and "content" not in response:
        response["content"] = "I couldn't process that request."
    return {"response": response}


async def update_memory_node(
    state: ConversationWorkflowState,
    memory_agent: Any,
) -> dict[str, Any]:
    if not memory_agent:
        return {}

    response = state.get("response") or {}
    messages = state.get("messages") or []

    try:
        if state.get("conversation_id"):
            await memory_agent.store(
                key="last_exchange",
                value={
                    "user": state.get("user_input"),
                    "assistant": response.get("content"),
                    "intent": response.get("intent"),
                },
                session_id=state.get("conversation_id"),
            )

        if state.get("customer_id") and state.get("store_id") and len(messages) >= 4:
            summary = await memory_agent.summarize(
                transcript="\n".join(f"{m.get('role')}: {m.get('content')}" for m in messages[-6:]),
                session_id=state.get("conversation_id"),
                user_id=state.get("customer_id"),
                store_id=state.get("store_id"),
            )
            trace = state.get("agent_trace") or []
            return {
                "agent_trace": [
                    *trace,
                    {"step": "memory", "summarized": bool(summary.get("summarized"))},
                ]
            }
    except Exception:
        logger.exception("update_memory failed")

    return {}


async def check_continuation_node(
    state: ConversationWorkflowState,
) -> dict[str, Any]:
    """Terminal node. Clarification loops continue across requests via the persisted conversation."""
    response = state.get("response") or {}
    response["needs_clarification"] = bool(response.get("needs_clarification"))
    return {"response": response, "current_turn": state.get("current_turn", 1) + 1}
