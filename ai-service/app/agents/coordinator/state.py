from typing import Any, NotRequired, TypedDict


class CoordinatorState(TypedDict):
    """State for the coordinator agent that routes user requests to sub-agents."""

    user_input: str
    intent: str | None
    confidence: float | None
    sub_agent: str | None
    conversation_id: str | None
    store_id: str
    customer_id: str | None
    context: dict[str, Any]
    response: dict[str, Any] | None
    needs_clarification: bool
    error: str | None
    metadata: NotRequired[dict[str, Any]]
