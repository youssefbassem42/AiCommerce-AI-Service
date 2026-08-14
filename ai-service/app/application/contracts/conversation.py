"""Canonical conversation-state structure for a single AI turn.

Documents every hop of one message: store, conversation, intent, retrieval,
agent result, and the final response. Used as the trace contract so a single
`message_id` can be followed end to end.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConversationTurnTrace(BaseModel):
    message_id: str
    request_id: str = ""
    store_id: str | None = None
    organization_id: str | None = None
    conversation_id: str | None = None
    customer_id: str | None = None
    history_count: int = 0
    intent: str | None = None
    confidence: float | None = None
    sub_agent: str | None = None
    retrieved_chunk_count: int = 0
    retrieval_strategy: str | None = None
    response_type: str | None = None
    product_count: int = 0
    bundle_present: bool = False
    promo_code_present: bool = False
    escalation_needed: bool = False
    model: str | None = None
    provider: str | None = None
    latency_ms: float = 0.0
    steps: list[dict[str, Any]] = Field(default_factory=list)
