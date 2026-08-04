from typing import Any, TypedDict


class ConversationWorkflowState(TypedDict, total=False):
    """State for the Conversation Workflow graph."""

    user_input: str
    messages: list[dict[str, Any]]
    current_turn: int
    max_turns: int
    context_window: int
    metadata: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    store_id: str | None
    customer_id: str | None
    conversation_id: str | None
    response: dict[str, Any] | None
    error: str | None
