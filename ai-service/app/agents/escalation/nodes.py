import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.escalation.state import EscalationState
from app.agents.escalation.tools import (
    assign_team,
    determine_tier,
    eta_hours_for_priority,
    resolve_priority,
)
from app.application.ticket.dto.escalation_dto import EscalationResponse
from app.application.ticket.dto.ticket_dto import TicketCreateDTO
from app.application.ticket.services.notification_service import TicketNotificationService
from app.application.ticket.services.ticket_service import TicketService
from app.core.ai_settings import ai_settings
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.infrastructure.prompts.client import get_prompt_client
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def _format_transcript(state: EscalationState) -> str:
    lines = []
    for msg in state.get("history") or []:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(c) for c in content)
        lines.append(f"{role}: {content}")
    if not lines:
        lines.append(f"customer: {state.get('user_query', '')}")
    return "\n".join(lines)


async def summarize_conversation_node(
    state: EscalationState,
    llm: BaseLLMProvider | None = None,
) -> dict[str, Any]:
    transcript = _format_transcript(state)
    reason = state.get("reason") or "The user requested human support."
    summary: str | None = None

    if llm:
        try:
            from app.application.dto.ai_dto import ChatRequest, MessageDTO

            request = ChatRequest(
                messages=[
                    MessageDTO(
                        role="system",
                        content="You write concise support handoff summaries. Return only the summary text.",
                    ),
                    MessageDTO(
                        role="user",
                        content=(await get_prompt_client().get("escalation.summarization_prompt")).format(
                            transcript=transcript, reason=reason
                        ),
                    ),
                ],
                model=ai_settings.DEFAULT_MODEL,
            )
            response = await llm.chat(request)
            content = response.message.content
            if isinstance(content, list):
                content = " ".join(str(item) for item in content)
            summary = (content or "").strip()
        except Exception as exc:
            logger.warning("Summarization failed: %s", exc, exc_info=True)

    if not summary:
        summary = f"{reason}\nConversation: {transcript[-800:]}"

    return {"summary": summary, "error": None}


async def determine_priority_node(
    state: EscalationState,
    customer_repo: ICustomerRepository | None = None,
) -> dict[str, Any]:
    tier = state.get("tier")
    if not tier and customer_repo and state.get("customer_id"):
        try:
            customer = await customer_repo.find_by_id(state["customer_id"])
            tier = determine_tier(customer)
        except Exception as exc:
            logger.warning("Tier lookup failed: %s", exc, exc_info=True)
            tier = "standard"
    tier = tier or "standard"

    priority = resolve_priority(state.get("category"), tier)
    eta = datetime.now(UTC) + timedelta(hours=eta_hours_for_priority(priority))
    return {"tier": tier, "priority": priority, "eta": eta, "error": None}


async def assign_team_node(state: EscalationState) -> dict[str, Any]:
    return {"assigned_to": assign_team(state.get("category")), "error": None}


async def notify_human_node(
    state: EscalationState,
    ticket_service: TicketService | None = None,
) -> dict[str, Any]:
    ticket_id = state.get("ticket_id")
    if not ticket_service:
        return {"ticket_id": ticket_id, "error": None, "persistence_success": False}

    try:
        if ticket_id:
            updated = await ticket_service.escalate_ticket(
                ticket_id=ticket_id,
                priority=state.get("priority"),
                assigned_to=state.get("assigned_to"),
                eta=state.get("eta"),
                message=state.get("summary"),
            )
            if updated is not None:
                ticket_id = updated.ticket_id
        else:
            created = await ticket_service.create_ticket(
                TicketCreateDTO(
                    store_id=state["store_id"],
                    customer_id=state.get("customer_id") or "",
                    conversation_id=state.get("conversation_id"),
                    messages=[state.get("user_query", ""), state.get("summary") or ""],
                )
            )
            ticket_id = created.ticket_id
            await ticket_service.escalate_ticket(
                ticket_id=ticket_id,
                priority=state.get("priority"),
                assigned_to=state.get("assigned_to"),
                eta=state.get("eta"),
            )
    except Exception as exc:
        logger.error("Ticket escalation failed: %s", exc, exc_info=True)
        return {
            "ticket_id": ticket_id,
            "error": f"Failed to escalate ticket: {exc}",
            "persistence_success": False,
        }

    return {"ticket_id": ticket_id, "error": None, "persistence_success": True}


async def notify_customer_node(
    state: EscalationState,
    notification_service: TicketNotificationService | None = None,
) -> dict[str, Any]:
    if not state.get("persistence_success"):
        return {"error": "Escalation not persisted; customer notification skipped."}
    if not notification_service:
        return {"error": None}

    priority = state.get("priority") or "p4"
    team = state.get("assigned_to") or "support"
    eta = state.get("eta")
    eta_suffix = (
        f" and you can expect a response within {eta.strftime('%H:%M UTC on %b %d')} (approximately "
        f"{eta_hours_for_priority(priority)} hours)"
        if eta
        else ""
    )
    message = (await get_prompt_client().get("escalation.notification_template")).format(
        team=team, eta_suffix=eta_suffix
    )

    try:
        await notification_service.create_notification(
            ticket_id=state.get("ticket_id") or "",
            store_id=state["store_id"],
            customer_id=state.get("customer_id") or "",
            message=message,
            eta=eta,
        )
        return {"notification_message": message, "error": None}
    except Exception as exc:
        logger.error("Customer notification failed: %s", exc, exc_info=True)
        return {"error": f"Failed to notify customer: {exc}"}


async def format_escalation_response_node(state: EscalationState) -> dict[str, Any]:
    persistence_success = bool(state.get("persistence_success"))
    response = EscalationResponse(
        query=state.get("user_query", ""),
        store_id=state.get("store_id", ""),
        customer_id=state.get("customer_id"),
        ticket_id=state.get("ticket_id") if persistence_success else None,
        category=state.get("category"),
        priority=state.get("priority"),
        assigned_to=state.get("assigned_to"),
        eta=state.get("eta"),
        summary=state.get("summary"),
        notification_message=state.get("notification_message") if persistence_success else None,
        error=state.get("error"),
        persistence_success=persistence_success,
    )
    return {"response": response}
