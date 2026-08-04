import json
import logging
from typing import Any

from app.agents.support.prompts import CATEGORIZE_PROMPT
from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SUPPORT_CATEGORIES = {"order_status", "returns", "refund", "technical", "account", "general"}

REFUNDABLE_FINANCIAL_STATUSES = {"paid", "partially_paid"}

REFUND_WINDOW_DAYS = 30

# Escalate when the refund exceeds this amount.
REFUND_ESCALATION_THRESHOLD = 500.0


async def categorize_issue(
    query: str,
    history: str = "",
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    """Classify the customer message into a support category."""
    default = {"category": "general", "confidence": 0.0, "order_relevant": False}
    if not llm:
        return default
    try:
        request = ChatRequest(
            messages=[
                MessageDTO(
                    role="system",
                    content="You categorize support messages. Return only valid JSON.",
                ),
                MessageDTO(
                    role="user",
                    content=CATEGORIZE_PROMPT.format(query=query, history=history[:1500]),
                ),
            ],
            model="gpt-4o-mini",
            json_mode=True,
        )
        response = await llm.structured_output(request, dict[str, Any])
        data = json.loads(response.message.content)
        if isinstance(data, dict) and data.get("category") in SUPPORT_CATEGORIES:
            return {
                "category": data["category"],
                "confidence": float(data.get("confidence", 0.0)),
                "order_relevant": bool(data.get("order_relevant", False)),
            }
    except Exception as exc:
        logger.error("Categorization failed: %s", exc, exc_info=True)
    return default


def format_order_for_tracking(order) -> dict[str, Any]:
    """Build a customer-safe summary of an order for tracking purposes."""
    total = order.total_price
    return {
        "id": order.id,
        "external_id": order.external_id,
        "financial_status": order.financial_status,
        "fulfillment_status": order.fulfillment_status,
        "currency": order.currency,
        "total": float(total.amount) if total else 0.0,
        "line_items": [{"title": li.title, "quantity": li.quantity} for li in (order.line_items or [])],
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def evaluate_refund_policy(order) -> dict[str, Any]:
    """Validate refund eligibility and calculate the refundable amount."""
    total = order.total_price
    total_amount = float(total.amount) if total else 0.0
    cancelled = order.cancelled_at is not None
    eligible = not cancelled and order.financial_status in REFUNDABLE_FINANCIAL_STATUSES and total_amount > 0
    return {
        "eligible": eligible,
        "amount": total_amount if eligible else None,
        "cancelled": cancelled,
        "financial_status": order.financial_status,
    }
