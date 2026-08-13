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
            history=state.get("context", {}).get("history") or [],
            conversation_id=state.get("conversation_id"),
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
                "result": _serialize_sub_agent_result(result),
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


def _serialize_product_card(product: Any) -> dict[str, Any] | None:
    """Consumer-safe product card from a sub-agent result DTO."""
    product_id = getattr(product, "product_id", None)
    title = getattr(product, "title", None)
    if not product_id and not title:
        return None
    specs = []
    for spec in getattr(product, "specs", None) or []:
        specs.append(
            {
                "name": getattr(spec, "name", None),
                "value": getattr(spec, "value", None),
            }
        )
    return {
        "product_id": str(product_id or ""),
        "title": title,
        "price": str(getattr(product, "price", "") or ""),
        "currency": getattr(product, "currency", "USD") or "USD",
        "image_url": getattr(product, "image_url", None),
        "product_url": getattr(product, "product_url", None),
        "specs": [s for s in specs if s.get("name") or s.get("value")][:12],
        "match_reasons": list(getattr(product, "match_reasons", None) or [])[:6],
    }


def _serialize_sub_agent_result(result: Any) -> dict[str, Any] | None:
    """Structured, consumer-safe snapshot of a sub-agent result.

    Only whitelisted fields are propagated; internal IDs and labels are never
    included here.
    """
    data: dict[str, Any] = {}

    products = getattr(result, "products", None)
    if isinstance(products, list) and products:
        cards = [c for c in (_serialize_product_card(p) for p in products) if c]
        if cards:
            data["products"] = cards

    bundles = getattr(result, "bundles", None)
    if isinstance(bundles, list) and bundles:
        bundle = _serialize_bundle(bundles)
        if bundle:
            data["bundle"] = bundle

    if getattr(result, "escalation_needed", False) or getattr(result, "ticket_id", None):
        data["ticket_created"] = bool(getattr(result, "ticket_id", None))
        data["escalation_needed"] = bool(getattr(result, "escalation_needed", False))

    if getattr(result, "clarifying_question", None):
        data["clarifying_question"] = str(result.clarifying_question)[:300]

    return data or None


def _serialize_bundle(bundles: list[Any]) -> dict[str, Any] | None:
    """First within-budget bundle candidate (or the first candidate) as a safe card."""
    candidates = [b for b in bundles if getattr(b, "within_budget", True)] or list(bundles)
    if not candidates:
        return None
    candidate = candidates[0]

    items = []
    for product in getattr(candidate, "products", None) or []:
        items.append(
            {
                "product_id": str(getattr(product, "product_id", "") or ""),
                "title": getattr(product, "product_title", None),
                "original_price": str(getattr(product, "original_price", "") or ""),
                "discount_pct": float(getattr(product, "discount_pct", 0.0) or 0.0),
                "price_after_discount": str(getattr(product, "price_after_discount", "") or ""),
            }
        )

    total_original = str(getattr(candidate, "total_original", "") or "")
    total_discount = str(getattr(candidate, "total_discount", "") or "")
    promo_code = getattr(candidate, "promo_code", None)

    return {
        "items": items,
        "total_original": total_original,
        "total_discount": total_discount,
        "promo_code": promo_code,
        "within_budget": bool(getattr(candidate, "within_budget", True)),
    }
