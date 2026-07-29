from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.domain.conversation.entities.message import Message
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class MessageDocument(BaseMongoDocument):
    """MongoDB document model representing a Message."""

    conversation_id: str = Field(..., index=True)
    role: str = Field(...)
    content: str = Field(...)
    sender: str = Field(...)
    sentiment: str | None = Field(None)
    intent: str | None = Field(None)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> Message:
        """Map the Mongo document back to domain Entity."""
        return Message(
            id=str(self.id),
            conversation_id=self.conversation_id,
            role=self.role,
            content=self.content,
            sender=self.sender,
            sentiment=self.sentiment,
            intent=self.intent,
            timestamp=self.timestamp,
            metadata=self.metadata,
        )

    @classmethod
    def from_entity(cls, entity: Message) -> "MessageDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            conversation_id=entity.conversation_id,
            role=entity.role,
            content=entity.content,
            sender=entity.sender,
            sentiment=entity.sentiment,
            intent=entity.intent,
            timestamp=entity.timestamp,
            metadata=entity.metadata,
        )
