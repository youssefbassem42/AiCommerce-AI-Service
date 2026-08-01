from typing import TypedDict

from app.application.ticket.dto.support_dto import SupportResponse


class SupportState(TypedDict):
    user_query: str
    store_id: str
    customer_id: str | None
    conversation_id: str | None
    history: list[dict]
    verified: bool
    customer: object | None
    issue_category: str | None
    order: object | None
    order_matches: list[object]
    resolution_steps: list[str]
    refund_info: object | None
    escalation_needed: bool
    escalation_reason: str | None
    ticket_id: str | None
    priority: str | None
    assigned_to: str | None
    eta: object | None
    satisfaction_question: str | None
    response: SupportResponse | None
    error: str | None
