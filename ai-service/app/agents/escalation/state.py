from datetime import datetime
from typing import TypedDict

from app.application.ticket.dto.escalation_dto import EscalationResponse


class EscalationState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    conversation_id: str | None
    history: list[dict]
    original_agent: str | None
    reason: str | None
    ticket_id: str | None
    category: str | None
    tier: str | None
    priority: str | None
    assigned_to: str | None
    eta: datetime | None
    summary: str | None
    notification_message: str | None
    response: EscalationResponse | None
    error: str | None
