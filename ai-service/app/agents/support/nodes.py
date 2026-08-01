import logging
from typing import Any

from app.agents.escalation.agent import EscalationAgent
from app.agents.support.state import SupportState
from app.agents.support.tools import (
    REFUND_ESCALATION_THRESHOLD,
    categorize_issue,
    evaluate_refund_policy,
    format_order_for_tracking,
)
from app.application.ticket.dto.support_dto import SupportResponse
from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.ticket_service import TicketService
from app.domain.commerce.repositories.order_repository import OrderRepository
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


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
    category = state.get("issue_category") or "general"
    verified = state.get("verified", False)
    refund_info = state.get("refund_info")

    escalation_needed = False
    reason: str | None = None

    if not verified:
        escalation_needed = True
        reason = "Customer identity could not be verified."
    elif category in ("technical", "account"):
        escalation_needed = True
        reason = f"Issue category '{category}' requires human assistance."
    elif refund_info and refund_info.get("eligible") and (refund_info.get("amount") or 0) > REFUND_ESCALATION_THRESHOLD:
        escalation_needed = True
        reason = f"Refund amount {refund_info['amount']:.2f} exceeds the auto-approval threshold."

    if not escalation_needed:
        return {
            "escalation_needed": False,
            "ticket_id": None,
            "priority": None,
            "assigned_to": None,
            "eta": None,
            "error": None,
        }

    ticket_id = state.get("ticket_id")
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
        except Exception as exc:
            logger.error("Ticket creation failed: %s", exc, exc_info=True)

    if escalation_agent:
        try:
            result = await escalation_agent.run(
                query=state["user_query"],
                store_id=state["store_id"],
                customer_id=state.get("customer_id"),
                history=state.get("history") or [],
                conversation_id=state.get("conversation_id"),
                original_agent="support",
                reason=reason,
                ticket_id=ticket_id,
                category=category,
            )
            return {
                "escalation_needed": True,
                "escalation_reason": reason,
                "ticket_id": result.ticket_id or ticket_id,
                "priority": result.priority,
                "assigned_to": result.assigned_to,
                "eta": result.eta,
                "error": None,
            }
        except Exception as exc:
            logger.error("Escalation agent failed: %s", exc, exc_info=True)
            return {
                "escalation_needed": True,
                "escalation_reason": reason,
                "ticket_id": ticket_id,
                "priority": None,
                "assigned_to": None,
                "eta": None,
                "error": f"Escalation failed: {exc}",
            }

    return {
        "escalation_needed": True,
        "escalation_reason": reason,
        "ticket_id": ticket_id,
        "priority": None,
        "assigned_to": None,
        "eta": None,
        "error": None,
    }


async def collect_feedback_node(state: SupportState) -> dict[str, Any]:
    if state.get("escalation_needed"):
        return {"satisfaction_question": None, "error": None}
    return {
        "satisfaction_question": "I hope that helped! Please rate your experience from 1 to 5 so we can improve.",
        "error": None,
    }


async def format_support_response_node(state: SupportState) -> dict[str, Any]:
    steps = list(state.get("resolution_steps") or [])
    category = state.get("issue_category") or "general"

    if state.get("escalation_needed"):
        rationale = (
            f"I'm handing this over to our {state.get('assigned_to') or 'support'} team"
            + (f" (priority {state.get('priority')})." if state.get("priority") else ".")
            + " A specialist will follow up with you shortly."
        )
    elif not steps and category == "general":
        rationale = "I'm not sure I can resolve this directly. Let me transfer you to a specialist who can help."
        steps.append("Transferred to a human specialist for assistance.")
    else:
        rationale = " ".join(steps) if steps else "How else can I help you today?"

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
    )
    return {"response": response}
