import logging
from collections.abc import Callable
from typing import Any

from bson import ObjectId

from app.agents.coordinator.state import CoordinatorState
from app.agents.coordinator.tools import (
    COMING_SOON_INTENTS,
    build_fallback_response,
    classify_intent,
    extract_context,
    format_history,
)
from app.domain.conversation.repositories.conversation_repository import ConversationRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

INTEGRATION_GUIDANCE = (
    "I can help with general integration questions. For detailed API connection setup, "
    "platform mapping, and sync management, please use the Integration section of the store dashboard."
)

SubAgentRunner = Callable[..., Any]


def _is_valid_object_id(value: str | None) -> bool:
    if not value:
        return False
    try:
        ObjectId(value)
        return True
    except Exception:
        return False


async def extract_context_node(
    state: CoordinatorState,
    conversation_repo: ConversationRepository | None = None,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Pull relevant context from conversation history and store profile."""
    history_messages: list[dict[str, Any]] = []
    if conversation_repo and _is_valid_object_id(state.get("conversation_id")):
        try:
            conversation = await conversation_repo.find_by_id(state["conversation_id"])
            if conversation:
                history_messages = [
                    {"role": m.role, "content": m.content}
                    for m in conversation.messages
                    if m.role in ("user", "assistant")
                ][-20:]
        except Exception as exc:
            logger.warning("Failed to load conversation history: %s", exc, exc_info=True)

    history_text = format_history(history_messages)
    store_profile: dict[str, Any] = {}

    try:
        extracted = await extract_context(
            user_input=state["user_input"],
            history=history_text,
            store_profile=store_profile,
            llm=llm,
        )
    except Exception as exc:
        logger.error("Context extraction failed: %s", exc, exc_info=True)
        extracted = {}

    return {
        "context": {
            "history": history_messages,
            "history_text": history_text,
            "store_profile": store_profile,
            "extracted": extracted,
        },
        "error": None,
    }


async def classify_intent_node(
    state: CoordinatorState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Analyze user input and classify into an intent with confidence."""
    try:
        intent, confidence = await classify_intent(
            user_input=state["user_input"],
            history=state.get("context", {}).get("history_text", ""),
            llm=llm,
        )
        return {"intent": intent, "confidence": confidence, "error": None}
    except Exception as exc:
        logger.error("Intent classification failed: %s", exc, exc_info=True)
        return {"intent": None, "confidence": None, "error": f"Intent classification failed: {exc}"}


async def route_to_agent_node(state: CoordinatorState) -> dict[str, Any]:
    """Return routing decision with confidence score."""
    intent = state.get("intent")
    if state.get("error") or not intent:
        return {"sub_agent": None, "needs_clarification": True}
    return {"sub_agent": intent, "needs_clarification": False}


async def execute_sub_agent_node(
    state: CoordinatorState,
    sub_agents: dict[str, SubAgentRunner] | None = None,
) -> dict[str, Any]:
    """Invoke the routed sub-agent graph and capture its response."""
    sub_agent = state.get("sub_agent")
    runner = (sub_agents or {}).get(sub_agent or "")
    if not runner:
        return {"error": f"Agent '{sub_agent}' is not registered", "needs_clarification": True}

    try:
        result = await runner(
            query=state["user_input"],
            store_id=state["store_id"],
            customer_id=state.get("customer_id"),
        )
        content = getattr(result, "rationale", None) or str(result)
        return {
            "response": {
                "content": content,
                "intent": state.get("intent"),
                "confidence": state.get("confidence"),
                "sub_agent": sub_agent,
                "needs_clarification": False,
                "citations": [],
            },
            "error": None,
        }
    except Exception as exc:
        logger.error("Sub-agent '%s' execution failed: %s", sub_agent, exc, exc_info=True)
        return {
            "response": {
                "content": f"Sorry, the {sub_agent} assistant ran into an issue. Please try again.",
                "intent": state.get("intent"),
                "confidence": state.get("confidence"),
                "sub_agent": sub_agent,
                "needs_clarification": False,
                "citations": [],
            },
            "error": f"Sub-agent execution failed: {exc}",
        }


async def handle_fallback_node(
    state: CoordinatorState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Graceful fallback when confidence is low or the agent is unavailable."""
    intent = state.get("intent")
    sub_agent = state.get("sub_agent")

    if sub_agent == "integration":
        content = INTEGRATION_GUIDANCE
        needs_clarification = False
    elif intent in COMING_SOON_INTENTS:
        content = await build_fallback_response(user_input=state["user_input"], intent=intent, llm=llm)
        needs_clarification = False
    else:
        content = await build_fallback_response(user_input=state["user_input"], intent=intent, llm=llm)
        needs_clarification = True

    return {
        "response": {
            "content": content,
            "intent": intent,
            "confidence": state.get("confidence"),
            "sub_agent": sub_agent,
            "needs_clarification": needs_clarification,
            "citations": [],
        },
        "error": None,
    }


async def format_response_node(state: CoordinatorState) -> dict[str, Any]:
    """Assemble the final response dict from the coordinator state."""
    if state.get("response") is not None:
        return {"response": state["response"], "error": None}

    return {
        "response": {
            "content": None,
            "intent": state.get("intent"),
            "confidence": state.get("confidence"),
            "sub_agent": state.get("sub_agent"),
            "needs_clarification": state.get("needs_clarification", False),
            "citations": [],
        },
        "error": None,
    }
