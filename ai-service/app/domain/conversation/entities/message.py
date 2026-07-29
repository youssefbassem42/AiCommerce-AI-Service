from datetime import datetime, UTC
from typing import Dict, Any, Optional
from pydantic import Field
from app.shared.kernel.entity import Entity

class Message(Entity[str]):
    """Domain representation of a conversation message."""
    conversation_id: str = Field(..., description="ID of the conversation this message belongs to")
    role: str = Field(..., description="Role of the message author (e.g. user, assistant, system)")
    content: str = Field(..., description="Text content of the message")
    sender: str = Field(..., description="Sender of the message (e.g. user, assistant, system)")
    sentiment: Optional[str] = Field(None, description="Sentiment of the message")
    intent: Optional[str] = Field(None, description="Intent of the message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When the message was sent")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata associated with the message")
