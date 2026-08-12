from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.analytics.entities.prompt_history import PromptHistory
from app.shared.kernel.aggregate_root import AggregateRoot


class AIRuntimeLog(AggregateRoot[str]):
    """Domain Aggregate Root for AI Runtime Logs capturing tracing, reasoning steps, and LLM calls."""

    conversation_id: str = Field(..., description="ID of the conversation associated with this execution log")
    model: str = Field(..., description="LLM model used")
    prompt_tokens: str = Field(..., description="Token used by prompt")
    latency: float = Field(..., description="Response latency")
    level: str = Field(default="INFO", description="Log level (INFO, WARN, ERROR)")
    message: str = Field(..., description="High-level description of what occurred")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured parameters/execution context")
    prompt_histories: list[PromptHistory] = Field(default_factory=list, description="LLM interactions during this step")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # --- AI usage accounting (spec §14) -------------------------------------
    store_id: str = Field(default="", description="Tenant store")
    organization_id: str = Field(default="", description="Tenant organization")
    billing_period: str = Field(default="", description="Subscription billing period identity")
    provider: str = Field(default="", description="Provider that executed the request")
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost: float = Field(default=0.0, ge=0.0)
    session_id: str = Field(default="", description="Consumer session identity (widget session token)")
