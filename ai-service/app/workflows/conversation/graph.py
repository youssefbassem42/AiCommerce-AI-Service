"""Conversation Workflow: orchestrates the coordinator, sub-agents, and memory agents."""

import logging
import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.coordinator.agent import CoordinatorAgent
from app.agents.coordinator.nodes import SubAgentRunner, format_knowledge_context
from app.application.contracts.intent import EXECUTABLE_INTENTS as CANONICAL_EXECUTABLE_INTENTS
from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.application.escalation.decision import evaluate_escalation
from app.core.ai_logging import log_flow_event
from app.core.ai_settings import ai_settings
from app.core.request_context import get_request_id
from app.infrastructure.providers.base import BaseLLMProvider
from app.workflows.conversation.state import ConversationWorkflowState

logger = logging.getLogger(__name__)

EXECUTABLE_INTENTS = {intent.value for intent in CANONICAL_EXECUTABLE_INTENTS}
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
        escalation_agent: Any | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
    ):
        self._coordinator = coordinator
        self._llm = llm
        self._sub_agents = sub_agents or {}
        self._memory_agent = memory_agent
        self._escalation_agent = escalation_agent
        self._max_turns = max_turns
        self._context_window = context_window
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        workflow = StateGraph(ConversationWorkflowState)

        workflow.add_node("validate_input", self._wrap(validate_input_node))
        workflow.add_node("recall_memory", self._wrap(recall_memory_node))
        workflow.add_node("update_shopping_state", self._wrap(update_shopping_state_node))
        workflow.add_node("route_to_agent", self._wrap(route_to_agent_node))
        workflow.add_node("execute_agent", self._wrap(execute_agent_node))
        workflow.add_node("evaluate_escalation", self._wrap(evaluate_escalation_node))
        workflow.add_node("format_response", self._wrap(format_response_node))
        workflow.add_node("update_memory", self._wrap(update_memory_node))
        workflow.add_node("check_continuation", self._wrap(check_continuation_node))

        workflow.set_entry_point("validate_input")
        workflow.add_conditional_edges(
            "validate_input",
            lambda state: "recall_memory" if not state.get("error") else "evaluate_escalation",
            {"recall_memory": "recall_memory", "evaluate_escalation": "evaluate_escalation"},
        )
        workflow.add_edge("recall_memory", "update_shopping_state")
        workflow.add_edge("update_shopping_state", "route_to_agent")
        workflow.add_conditional_edges(
            "route_to_agent",
            route_after_route,
            {
                "execute_agent": "execute_agent",
                "evaluate_escalation": "evaluate_escalation",
            },
        )
        workflow.add_edge("execute_agent", "evaluate_escalation")
        workflow.add_edge("evaluate_escalation", "format_response")
        workflow.add_edge("format_response", "update_memory")
        workflow.add_edge("update_memory", "check_continuation")
        workflow.add_edge("check_continuation", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: ConversationWorkflowState) -> dict[str, Any]:
            extra: dict[str, Any] = {}
            if node_fn in (recall_memory_node, update_shopping_state_node, update_memory_node):
                extra["memory_agent"] = self._memory_agent
            if node_fn == update_shopping_state_node:
                extra["llm"] = self._llm
            elif node_fn == route_to_agent_node:
                extra["coordinator"] = self._coordinator
            elif node_fn == execute_agent_node:
                extra["llm"] = self._llm
                extra["sub_agents"] = self._sub_agents
            elif node_fn == evaluate_escalation_node:
                extra["escalation_agent"] = self._escalation_agent
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
        context: dict[str, Any] | None = None,
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
            "message_id": (metadata or {}).get("message_id"),
            "context": context or {},
            "response": None,
            "error": None,
        }

        result = await self._graph.ainvoke(initial_state)
        response = result.get("response") or {}
        escalation = result.get("escalation")

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
                "result": response.get("result"),
                "trace": result.get("agent_trace", []),
                "message_id": (metadata or {}).get("message_id"),
                "request_id": get_request_id(),
                "escalation": escalation,
            },
        )


def route_after_route(state: ConversationWorkflowState) -> str:
    response = state.get("response") or {}
    intent = response.get("intent")
    if intent == "general" and response.get("content") is None:
        return "execute_agent"
    return "evaluate_escalation"


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


async def recall_memory_node(
    state: ConversationWorkflowState,
    memory_agent: Any,
) -> dict[str, Any]:
    """Recall session/user memory into the context before any reasoning.

    Runs once per turn: when the Context Builder already recalled memory
    (widget path) it is reused; otherwise (plain chat path) it is loaded
    here so sub-agents always see the customer's remembered context.
    """
    if not memory_agent or not state.get("conversation_id"):
        return {}

    context = dict(state.get("context") or {})
    memory = context.get("memory") or {}
    if memory.get("entries") or memory.get("recall_source"):
        return {}

    try:
        result = await memory_agent.recall(
            session_id=state.get("conversation_id"),
            user_id=state.get("customer_id"),
            store_id=state.get("store_id"),
        )
        retrieved = result.get("retrieved") or {}
        context["memory"] = {
            "recall_source": retrieved.get("source"),
            "entries": retrieved.get("all") or (retrieved if "all" not in retrieved else {}),
        }
        return {"context": context}
    except Exception:
        logger.exception("recall_memory failed")
        return {}


async def update_shopping_state_node(
    state: ConversationWorkflowState,
    memory_agent: Any,
    llm: Any,
) -> dict[str, Any]:
    """Merge constraints: extract the latest message into shopping state.

    The current state comes from recalled memory; the latest message is
    interpreted in that context and merged incrementally (Fix 3.3). The
    merged state is persisted as session-scoped memory (short-term) and
    injected into the context so sub-agents receive it (Fix 3.5).
    """
    from app.agents.memory.tools import extract_shopping_state
    from app.application.context.shopping_state import (
        SESSION_STATE_KEY,
        ShoppingState,
    )

    context = dict(state.get("context") or {})
    memory = context.get("memory") or {}
    entries = memory.get("entries") if isinstance(memory, dict) else None
    current = ShoppingState.from_dict(entries.get(SESSION_STATE_KEY) if isinstance(entries, dict) else None)

    messages = list(state.get("messages") or [])
    history_text = "\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in messages[-6:])

    update = await extract_shopping_state(
        user_input=state.get("user_input") or "",
        history=history_text,
        current_state=current.to_dict(),
        llm=llm,
    )
    merged = current.merge(update)
    if merged.is_empty():
        return {}

    if memory_agent and state.get("conversation_id"):
        try:
            await memory_agent.store(
                key=SESSION_STATE_KEY,
                value=merged.to_dict(),
                session_id=state.get("conversation_id"),
            )
        except Exception:
            logger.exception("shopping state persist failed")

    conversation = dict(context.get("conversation") or {})
    conversation[SESSION_STATE_KEY] = merged.to_dict()
    context["conversation"] = conversation

    return {"context": context}


async def route_to_agent_node(
    state: ConversationWorkflowState,
    coordinator: CoordinatorAgent,
) -> dict[str, Any]:
    coordinator_result = await coordinator.run(
        user_input=state["user_input"],
        store_id=state.get("store_id") or "",
        conversation_id=state.get("conversation_id"),
        customer_id=state.get("customer_id"),
        context=state.get("context") or {},
        metadata=state.get("metadata"),
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
                    history=messages,
                    conversation_id=state.get("conversation_id"),
                    context=state.get("context") or {},
                )
                rationale = getattr(result, "rationale", None)
                notification = getattr(result, "notification_message", None)
                if rationale:
                    response["content"] = rationale
                elif notification:
                    response["content"] = notification
                else:
                    response["content"] = str(result)
                response["data"] = getattr(result, "model_dump", lambda: {})() if hasattr(result, "model_dump") else {}
                if getattr(result, "escalation_needed", False) or getattr(result, "ticket_id", None):
                    response["escalation_needed"] = True
                    response["ticket_id"] = getattr(result, "ticket_id", None) or response.get("ticket_id")
        else:
            knowledge_text = format_knowledge_context(state.get("context") or {})
            system_content = "You are a helpful e-commerce assistant."
            if knowledge_text:
                system_content = (
                    f"You are a helpful e-commerce assistant. Use the store context below to answer "
                    f"knowledge and policy questions accurately.\n\n{knowledge_text}"
                )
            request = ChatRequest(
                messages=[
                    MessageDTO(role="system", content=system_content),
                    *[MessageDTO(role=m.get("role", "user"), content=m.get("content", "")) for m in messages],
                ],
                model=ai_settings.DEFAULT_MODEL,
            )
            reply = await llm.chat(request)
            response["content"] = reply.message.content
        log_flow_event(
            "agent.result",
            message_id=state.get("message_id"),
            store_id=store_id,
            conversation_id=state.get("conversation_id"),
            intent=intent,
            sub_agent=intent,
            error=None,
        )
    except Exception:
        logger.exception("execute_agent failed")
        response["content"] = "I ran into an issue while answering. Please try again."
        log_flow_event(
            "agent.error",
            message_id=state.get("message_id"),
            store_id=store_id,
            conversation_id=state.get("conversation_id"),
            intent=intent,
        )

    trace = list(state.get("agent_trace") or [])
    trace.append({"step": "execute_agent", "intent": intent})
    return {"response": response, "agent_trace": trace}


def _handoff_message(decision: dict[str, Any]) -> str:
    team = "support"
    priority = decision.get("priority")
    suffix = f" (priority {priority.upper()})" if priority else ""
    return (
        f"I'm handing this over to our {team} team{suffix} so a specialist can take a closer look. "
        "They will follow up with you shortly."
    )


async def evaluate_escalation_node(
    state: ConversationWorkflowState,
    escalation_agent: Any | None = None,
) -> dict[str, Any]:
    """Last-resort escalation check after the AI attempted resolution.

    Runs the deterministic decision engine against the latest turn. If the
    turn already escalated (escalation intent, support agent, direct ticket),
    the existing decision is kept. Otherwise, when the decision engine fires
    on one of its signals (explicit human request, knowledge unavailable,
    repeated failure, strong frustration, business rule), a ticket is created
    through the escalation agent and the reply is replaced with the handoff
    message. Identity (customer_id) never triggers escalation.
    """
    response = dict(state.get("response") or {})
    data = response.get("data") or {}
    already_escalated = bool(
        response.get("escalation_needed")
        or response.get("ticket_id")
        or data.get("escalation_needed")
        or data.get("ticket_id")
    )

    user_input = state.get("user_input") or ""
    if not user_input:
        return {}

    if already_escalated:
        decision = {
            "should_escalate": True,
            "reason": response.get("escalation_reason") or data.get("escalation_reason") or "Escalated by sub-agent.",
            "confidence": 1.0,
            "priority": response.get("priority") or data.get("priority"),
            "signals": [],
            "summary": None,
            "category": response.get("intent"),
            "ticket_id": response.get("ticket_id") or data.get("ticket_id"),
            "assigned_to": response.get("assigned_to") or data.get("assigned_to"),
            "eta": response.get("eta") or data.get("eta"),
        }
        trace = list(state.get("agent_trace") or [])
        trace.append({"step": "evaluate_escalation", "should_escalate": True, "source": "sub_agent"})
        return {"escalation": decision, "agent_trace": trace}

    messages = list(state.get("messages") or [])
    history = [m for m in messages[:-1] if m.get("role") == "user"]
    context = state.get("context") or {}
    knowledge_available = bool(context.get("knowledge_context")) or bool(context.get("business_rules"))

    decision = evaluate_escalation(
        user_input=user_input,
        history=history,
        category=response.get("intent") or (state.get("context") or {}).get("intent"),
        knowledge_available=knowledge_available,
        answered=bool(response.get("content")),
        customer_id=state.get("customer_id"),
    )

    trace = list(state.get("agent_trace") or [])
    if not decision.should_escalate:
        trace.append({"step": "evaluate_escalation", "should_escalate": False, "signals": []})
        return {"escalation": decision.model_dump(), "agent_trace": trace}

    decision_dict = decision.model_dump()
    if escalation_agent:
        try:
            result = await escalation_agent.run(
                query=user_input,
                store_id=state.get("store_id") or "",
                customer_id=state.get("customer_id"),
                history=messages,
                conversation_id=state.get("conversation_id"),
                original_agent="workflow",
                reason=decision.reason,
                category=decision.category,
            )
            if result.ticket_id:
                decision_dict["ticket_id"] = result.ticket_id
            if result.priority:
                decision_dict["priority"] = result.priority
            if result.assigned_to:
                decision_dict["assigned_to"] = result.assigned_to
            if result.eta:
                decision_dict["eta"] = str(result.eta)
            response["content"] = result.notification_message or _handoff_message(decision_dict)
            response["escalation_needed"] = True
            response["escalation_reason"] = decision.reason
            response["ticket_id"] = decision_dict.get("ticket_id")
        except Exception:
            logger.exception("evaluate_escalation: escalation agent failed")
            decision_dict["should_escalate"] = False
            decision_dict["signals"] = []
            decision_dict["reason"] = None
            response["content"] = response.get("content") or (
                "I'm not able to resolve this from the information I have. "
                "Please contact the store's support team for help."
            )
    else:
        # No handoff path configured: record the decision for observability but
        # keep the AI's answer - never claim a transfer that did not happen.
        decision_dict["should_escalate"] = False
        decision_dict["signals"] = []
        decision_dict["reason"] = None
        response["content"] = response.get("content") or (
            "I'm not able to resolve this from the information I have. "
            "Please contact the store's support team for help."
        )

    trace.append(
        {
            "step": "evaluate_escalation",
            "should_escalate": decision_dict.get("should_escalate", False),
            "signals": decision_dict.get("signals", []),
            "confidence": decision_dict.get("confidence", 0.0),
        }
    )
    return {"response": response, "escalation": decision_dict, "agent_trace": trace}


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
