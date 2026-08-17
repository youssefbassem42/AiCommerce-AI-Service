import logging
from typing import Any

from app.agents.escalation.agent import EscalationAgent
from app.agents.support.state import SupportState
from app.agents.support.tools import (
    REFUND_ESCALATION_THRESHOLD,
    categorize_issue,
    detect_topic,
    evaluate_refund_policy,
    facts_from_context,
    format_facts_for_prompt,
    format_memory_for_prompt,
    format_order_for_prompt,
    format_order_for_tracking,
    retrieve_support_facts,
    search_product_cards,
)
from app.application.contracts.escalation import build_escalation_decision as _build_decision
from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.escalation.decision import BUSINESS_RULE, evaluate_escalation
from app.application.ticket.dto.support_dto import SupportResponse
from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.core.ai_settings import ai_settings
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

PRODUCT_TOPICS = {"product"}


async def verify_customer_node(
    state: SupportState,
    customer_repo: ICustomerRepository | None = None,
) -> dict[str, Any]:
    customer = None
    verified = False
    if customer_repo and state.get("customer_id"):
        try:
            customer = await customer_repo.find_by_id(state["customer_id"])
            verified = customer is not None
        except Exception as exc:
            logger.warning("Customer verification failed: %s", exc, exc_info=True)

    if not verified:
        return {
            "verified": False,
            "customer": None,
            "error": "Unable to verify the customer.",
        }
    return {"verified": True, "customer": customer, "error": None}


async def categorize_issue_node(
    state: SupportState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    history_text = "\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in (state.get("history") or []))[-1500:]
    result = await categorize_issue(state["user_query"], history=history_text, llm=llm)
    return {"issue_category": result["category"], "error": None}


async def retrieve_facts_node(
    state: SupportState,
    llm: BaseLLMProvider | None = None,
    retriever_service: Any | None = None,
    product_repo: Any | None = None,
) -> dict[str, Any]:
    """Intent-specific knowledge retrieval (Fix 6.1) and product resolution (Fix 6.4).

    Detects the support topic, retrieves the matching store facts (return/shipping/
    payment/warranty policy), and resolves the actual product when the customer
    asks about specs. Facts are stored as verified facts for grounded answering.
    """
    query = state["user_query"]
    history_text = "\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in (state.get("history") or []))[-1500:]
    context = state.get("context") or {}

    topic_result = await detect_topic(query, history=history_text, llm=llm)
    topic = topic_result.get("topic") or "general"

    facts = await retrieve_support_facts(
        query,
        topic,
        store_id=state["store_id"],
        retriever_service=retriever_service,
        context=context,
    )
    if not facts:
        facts = facts_from_context(context)

    product_matches: list[dict[str, Any]] = []
    product: dict[str, Any] | None = None
    if topic in PRODUCT_TOPICS or (topic_result.get("product_mention") and state.get("issue_category") == "general"):
        product_matches = await search_product_cards(
            product_repo,
            state["store_id"],
            topic_result.get("product_mention") or query,
        )
        if product_matches:
            product = product_matches[0]

    return {
        "topic": topic,
        "verified_facts": facts,
        "product": product,
        "product_matches": product_matches,
        "error": None,
    }


async def resolve_order_issue_node(
    state: SupportState,
    order_repo: OrderRepository | None = None,
) -> dict[str, Any]:
    category = state.get("issue_category") or "general"
    if category not in ("order_status", "returns", "refund"):
        return {"order_matches": [], "order": None, "resolution_steps": [], "error": None}

    if not order_repo or not state.get("customer_id"):
        return {
            "order_matches": [],
            "order": None,
            "resolution_steps": ["I couldn't locate your order. Please contact support for assistance."],
            "error": None,
        }

    try:
        orders = await order_repo.find_by_customer(state["customer_id"], limit=5)
        orders = [o for o in orders if o.store_id == state["store_id"]]
        order = orders[0] if orders else None

        steps: list[str] = []
        if not order:
            steps.append("I couldn't find any orders under this account.")
        elif category == "order_status":
            info = format_order_for_tracking(order)
            steps.append(
                f"Order {order.external_id or order.id} is {info['fulfillment_status'] or 'in progress'} "
                f"with financial status {info['financial_status']}."
            )
            items = ", ".join(f"{li['quantity']}x {li['title']}" for li in info["line_items"])
            if items:
                steps.append(f"Items in this order: {items}.")
        elif category == "returns":
            steps.append(
                "You can request a return from the order page in your account. "
                "I can log this for the store team to prepare a return label."
            )
        return {"order_matches": orders, "order": order, "resolution_steps": steps, "error": None}
    except Exception as exc:
        logger.error("Order lookup failed: %s", exc, exc_info=True)
        return {
            "order_matches": [],
            "order": None,
            "resolution_steps": ["I couldn't load your order details right now."],
            "error": f"Order lookup failed: {exc}",
        }


async def handle_refund_node(state: SupportState) -> dict[str, Any]:
    category = state.get("issue_category") or "general"
    if category != "refund":
        return {"refund_info": None, "resolution_steps": [], "error": None}

    order = state.get("order")
    steps: list[str] = []
    refund_info: dict[str, Any] | None = None

    if not order:
        steps.append("To process a refund I need to locate your order. Please share your order number.")
        return {"refund_info": None, "resolution_steps": steps, "error": None}

    refund_info = evaluate_refund_policy(order)
    if refund_info["eligible"]:
        steps.append(
            f"Your order is eligible for a refund of {refund_info['amount']:.2f} {order.currency}. "
            "The store team will process the refund back to your original payment method."
        )
    else:
        reason = "cancelled" if refund_info["cancelled"] else f"status is {refund_info['financial_status']}"
        steps.append(f"Unfortunately this order is not eligible for a refund because the order {reason}.")

    return {"refund_info": refund_info, "resolution_steps": steps, "error": None}


async def escalate_if_needed_node(
    state: SupportState,
    escalation_agent: EscalationAgent | None = None,
    ticket_service: TicketService | None = None,
) -> dict[str, Any]:
    """Last-resort escalation decision (Phase 7).

    Delegates to the shared decision engine: escalation fires only on one of
    the explicit signals (explicit human request, knowledge unavailable,
    repeated failure, strong frustration, business rule). Identity is never
    a trigger - an unverified or anonymous customer still gets a resolution
    attempt instead of an automatic ticket.
    """
    category = state.get("issue_category") or "general"
    refund_info = state.get("refund_info")

    history = [m for m in (state.get("history") or []) if m.get("role") == "user"]
    decision = evaluate_escalation(
        user_input=state["user_query"],
        history=history,
        category=category,
        knowledge_available=bool(state.get("verified_facts")),
        answered=bool(state.get("resolution_steps")) or bool(state.get("order")),
        customer_id=state.get("customer_id"),
    )

    if refund_info and refund_info.get("eligible") and (refund_info.get("amount") or 0) > REFUND_ESCALATION_THRESHOLD:
        decision = _build_decision(
            should_escalate=True,
            reason=f"Refund amount {refund_info['amount']:.2f} exceeds the auto-approval threshold.",
            confidence=0.9,
            priority=decision.priority or "p2",
            signals=[*decision.signals, BUSINESS_RULE],
            summary="Refund exceeds the auto-approval threshold.",
            category=category,
        )

    if not decision.should_escalate:
        return {
            "escalation_needed": False,
            "escalation_reason": None,
            "ticket_id": None,
            "priority": None,
            "assigned_to": None,
            "eta": None,
            "error": None,
            "persistence_success": True,
        }

    ticket_id = state.get("ticket_id")
    persistence_success = False
    if ticket_service:
        try:
            created = await ticket_service.create_ticket(
                TicketCreateDTO(
                    store_id=state["store_id"],
                    customer_id=state.get("customer_id") or "",
                    conversation_id=state.get("conversation_id"),
                    messages=[
                        *[str(m.get("content", "")) for m in (state.get("history") or [])[-10:]],
                        state["user_query"],
                    ],
                )
            )
            ticket_id = created.ticket_id
            persistence_success = True
        except Exception as exc:
            logger.error("Ticket creation failed: %s", exc, exc_info=True)
            return {
                "escalation_needed": True,
                "escalation_reason": decision.reason,
                "ticket_id": None,
                "priority": decision.priority,
                "assigned_to": None,
                "eta": None,
                "error": f"Ticket creation failed: {exc}",
                "persistence_success": False,
            }

    if escalation_agent:
        try:
            result = await escalation_agent.run(
                query=state["user_query"],
                store_id=state["store_id"],
                customer_id=state.get("customer_id"),
                history=state.get("history") or [],
                conversation_id=state.get("conversation_id"),
                original_agent="support",
                reason=decision.reason,
                ticket_id=ticket_id,
                category=category,
            )
            return {
                "escalation_needed": True,
                "escalation_reason": decision.reason,
                "ticket_id": result.ticket_id or ticket_id,
                "priority": result.priority or decision.priority,
                "assigned_to": result.assigned_to,
                "eta": result.eta,
                "error": None,
                "persistence_success": persistence_success,
            }
        except Exception as exc:
            logger.error("Escalation agent failed: %s", exc, exc_info=True)
            return {
                "escalation_needed": True,
                "escalation_reason": decision.reason,
                "ticket_id": ticket_id,
                "priority": decision.priority,
                "assigned_to": None,
                "eta": None,
                "error": f"Escalation failed: {exc}",
                "persistence_success": persistence_success,
            }

    return {
        "escalation_needed": True,
        "escalation_reason": decision.reason,
        "ticket_id": ticket_id,
        "priority": decision.priority,
        "assigned_to": None,
        "eta": None,
        "error": None,
        "persistence_success": persistence_success,
    }


async def collect_feedback_node(state: SupportState) -> dict[str, Any]:
    if state.get("escalation_needed"):
        return {"satisfaction_question": None, "error": None}
    return {
        "satisfaction_question": "I hope that helped! Please rate your experience from 1 to 5 so we can improve.",
        "error": None,
    }


async def format_support_response_node(state: SupportState) -> dict[str, Any]:
    """Legacy template formatter (kept for the fallback path)."""
    return await generate_response_node(state, llm=None)


async def generate_response_node(
    state: SupportState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Humanized, grounded response generation (Fix 6.2 + 6.3).

    The LLM receives verified facts + conversation + memory and writes a natural
    reply. Policy grounding is enforced by the prompt (never invent facts) and
    by only feeding retrieved store facts. Falls back to the deterministic
    template when the LLM is unavailable.
    """
    steps = list(state.get("resolution_steps") or [])
    category = state.get("issue_category") or "general"
    topic = state.get("topic") or "general"
    facts = list(state.get("verified_facts") or [])
    product = state.get("product")
    memory = state.get("memory") or {}

    if state.get("escalation_needed"):
        if state.get("persistence_success"):
            rationale = _escalation_message(state)
        else:
            rationale = (
                "I'd like to have a specialist follow up with you, but I'm having "
                "trouble submitting the request right now. Please try again in a moment, "
                "or contact the store's support team directly."
            )
        return _build_response(state, steps, category, rationale)

    if product:
        facts = [*facts, {"source": "Store catalog", "content": _product_fact_text(product)}]

    if llm and (facts or steps or state.get("order")):
        try:
            rationale = await _generate_grounded_reply(state, facts, memory, llm)
            return _build_response(state, steps, category, rationale)
        except Exception as exc:
            logger.warning("Grounded reply generation failed, using fallback: %s", exc, exc_info=True)

    rationale = _template_reply(state, steps, category, topic)
    return _build_response(state, steps, category, rationale)


def _escalation_message(state: SupportState) -> str:
    return (
        f"I'm handing this over to our {state.get('assigned_to') or 'support'} team"
        + (f" (priority {state.get('priority')})." if state.get("priority") else ".")
        + " A specialist will follow up with you shortly."
    )


def _template_reply(state: SupportState, steps: list[str], category: str, topic: str) -> str:
    """Deterministic fallback used when the LLM is unavailable."""
    if steps:
        return " ".join(steps)
    if category == "general" and not state.get("verified_facts"):
        return "I'm not able to resolve this from the information I have. Please contact the store's support team for help."
    if category == "general" and state.get("verified_facts"):
        return "Here's what I found from the store's policies. If you need more detail, feel free to ask."
    return "How else can I help you today?"


def _product_fact_text(product: dict[str, Any]) -> str:
    lines = [f"Product: {product.get('title', '')}"]
    if product.get("description"):
        lines.append(f"Description: {product['description']}")
    if product.get("price") is not None:
        lines.append(f"Price: {product['price']} {product.get('currency', 'USD')}")
    if product.get("product_type"):
        lines.append(f"Type: {product['product_type']}")
    variants = product.get("variants") or []
    for variant in variants[:4]:
        lines.append(
            f"Variant '{variant.get('title', '')}': SKU {variant.get('sku', '-')}, "
            f"price {variant.get('price')} {variant.get('currency', product.get('currency', 'USD'))}, "
            f"stock {variant.get('inventory_quantity', 0)}"
        )
    return "\n".join(lines)


async def _generate_grounded_reply(
    state: SupportState,
    facts: list[dict[str, Any]],
    memory: dict[str, Any],
    llm: BaseLLMProvider,
) -> str:
    order = state.get("order")
    conversation_lines = [f"{m.get('role')}: {m.get('content', '')}" for m in (state.get("history") or [])]
    conversation_lines.append(f"user: {state['user_query']}")

    prompt = await get_prompt_client().get("support.reply_prompt")
    request = ChatRequest(
        messages=[
            MessageDTO(
                role="system",
                content=prompt.format(
                    facts=format_facts_for_prompt(facts),
                    order_details=format_order_for_prompt(order),
                    memory=format_memory_for_prompt(memory),
                    conversation="\n".join(conversation_lines[-12:]),
                ),
            ),
            MessageDTO(role="user", content=state["user_query"]),
        ],
        model=ai_settings.DEFAULT_MODEL,
        temperature=0.4,
        max_tokens=500,
    )
    response = await llm.chat(request)
    content = response.message.content
    if isinstance(content, list):
        content = " ".join(str(item) for item in content)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("LLM returned an empty or non-string reply")
    return content.strip()


def _build_response(
    state: SupportState,
    steps: list[str],
    category: str,
    rationale: str,
) -> dict[str, Any]:
    question = state.get("satisfaction_question")
    if question and not state.get("escalation_needed"):
        rationale = f"{rationale} {question}"

    response = SupportResponse(
        query=state.get("user_query", ""),
        store_id=state.get("store_id", ""),
        customer_id=state.get("customer_id"),
        verified=state.get("verified", False),
        issue_category=category,
        resolution_steps=steps,
        escalation_needed=state.get("escalation_needed", False),
        escalation_reason=state.get("escalation_reason"),
        ticket_id=state.get("ticket_id"),
        priority=state.get("priority"),
        assigned_to=state.get("assigned_to"),
        eta=state.get("eta"),
        rationale=rationale,
        error=state.get("error"),
        products=list(state.get("product_matches") or []),
    )
    return {"response": response}
