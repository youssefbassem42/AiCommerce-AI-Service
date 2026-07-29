from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.shared.kernel.entity import Entity


class Message(Entity[str]):
    """Domain representation of a conversation message."""

    conversation_id: str = Field(..., description="ID of the conversation this message belongs to")
    role: str = Field(..., description="Role of the message author (e.g. user, assistant, system)")
    content: str = Field(..., description="Text content of the message")
    sender: str = Field(..., description="Sender of the message (e.g. user, assistant, system)")
    sentiment: str | None = Field(None, description="Sentiment of the message")
    intent: str | None = Field(None, description="Intent of the message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When the message was sent")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata associated with the message")
