"""Canonical AI response schema for a chat turn.

Every entry point (widget, chat API, RAG) should be able to express its
answer as an `AITurnContract`: the reply text, optional product/bundle
payloads, the intent that produced it, and the trace of hops.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.application.contracts.bundle import BundlePayload
from app.application.contracts.product import ProductPayload


class AITurnContract(BaseModel):
    message_id: str
    request_id: str = ""
    store_id: str | None = None
    organization_id: str | None = None
    conversation_id: str | None = None
    customer_id: str | None = None
    intent: str | None = None
    confidence: float | None = None
    sub_agent: str | None = None
    response_type: str = "text"
    response: str
    products: list[ProductPayload] = Field(default_factory=list)
    product: ProductPayload | None = None
    bundle: BundlePayload | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    provider: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    trace: list[dict[str, Any]] = Field(default_factory=list)
