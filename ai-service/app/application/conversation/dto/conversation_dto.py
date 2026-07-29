from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MessageDTO(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sender: str
    sentiment: str | None = None
    intent: str | None = None
    timestamp: datetime
    metadata: dict[str, Any]


class ConversationDTO(BaseModel):
    id: str
    customer_id: str
    store_id: str
    status: str
    messages: list[MessageDTO]
    created_at: datetime
    updated_at: datetime
