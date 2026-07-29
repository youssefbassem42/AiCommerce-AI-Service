from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class MessageDTO(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    sender: str
    sentiment: Optional[str] = None
    intent: Optional[str] = None
    timestamp: datetime
    metadata: Dict[str, Any]

class ConversationDTO(BaseModel):
    id: str
    customer_id: str
    store_id: str
    status: str
    messages: List[MessageDTO]
    created_at: datetime
    updated_at: datetime
