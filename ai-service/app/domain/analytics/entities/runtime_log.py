from datetime import datetime, UTC
from typing import List, Dict, Any
from pydantic import Field
from app.shared.kernel.aggregate_root import AggregateRoot
from app.domain.analytics.entities.prompt_history import PromptHistory

class AIRuntimeLog(AggregateRoot[str]):
    """Domain Aggregate Root for AI Runtime Logs capturing tracing, reasoning steps, and LLM calls."""
    conversation_id: str = Field(..., description="ID of the conversation associated with this execution log")
    model: str = Field(..., description="LLM model used")
    prompt_tokens: str = Field(..., description="Token used by prompt")
    latency: float = Field(..., description="Response latency")
    level: str = Field(default="INFO", description="Log level (INFO, WARN, ERROR)")
    message: str = Field(..., description="High-level description of what occurred")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured parameters/execution context")
    prompt_histories: List[PromptHistory] = Field(default_factory=list, description="LLM interactions during this step")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
