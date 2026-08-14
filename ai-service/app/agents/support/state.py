from typing import Any, NotRequired, TypedDict

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
    topic: NotRequired[str | None]
    verified_facts: NotRequired[list[dict[str, Any]]]
    product: NotRequired[dict[str, Any] | None]
    product_matches: NotRequired[list[dict[str, Any]]]
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
    memory: NotRequired[dict[str, Any]]
    customer_profile: NotRequired[dict[str, Any] | None]
    context: NotRequired[dict[str, Any] | None]
