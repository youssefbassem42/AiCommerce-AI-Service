from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PromptHistoryDTO(BaseModel):
    id: str
    runtimeId: str
    provider: str
    context: str
    model: str
    system_prompt: str
    user_prompt: str
    llm_response: str
    token_used: int
    timestamp: datetime


class AIRuntimeLogDTO(BaseModel):
    id: str
    conversation_id: str
    model: str
    prompt_tokens: str
    latency: float
    level: str
    message: str
    details: dict[str, Any]
    prompt_histories: list[PromptHistoryDTO]
    timestamp: datetime


class DashboardInsightDTO(BaseModel):
    id: str
    store_id: str
    recommendations: list[str]
    metadata: dict[str, Any]
    calculated_at: datetime


class SentimentSummaryDTO(BaseModel):
    store_id: str
    total: int
    positive_count: int
    neutral_count: int
    negative_count: int
    positive_pct: float
    neutral_pct: float
    negative_pct: float
