from datetime import datetime
from typing import List, Dict, Any
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
    details: Dict[str, Any]
    prompt_histories: List[PromptHistoryDTO]
    timestamp: datetime

class DashboardInsightDTO(BaseModel):
    id: str
    store_id: str
    recommendations: List[str]
    metadata: Dict[str, Any]
    calculated_at: datetime
