from datetime import datetime, UTC
from typing import List, Optional
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.infrastructure.mongodb.documents.message_document import MessageDocument
from app.domain.conversation.entities.conversation import Conversation

class ConversationDocument(BaseMongoDocument):
    """MongoDB document model representing a Conversation."""
    customer_id: str = Field(..., index=True)
    store_id: str = Field(..., index=True)
    status: str = Field(default="active")
    messages: Optional[List[MessageDocument]] = Field(default=None, exclude=True)

    def to_entity(self) -> Conversation:
        """Map the Mongo document back to domain Entity."""
        entity = Conversation(
            id=str(self.id),
            customer_id=self.customer_id,
            store_id=self.store_id,
            status=self.status,
            messages=[msg.to_entity() for msg in self.messages] if self.messages else [],
            created_at=self.created_at,
            updated_at=self.updated_at
        )
        return entity

    @classmethod
    def from_entity(cls, entity: Conversation) -> "ConversationDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            _id=entity.id,
            customer_id=entity.customer_id,
            store_id=entity.store_id,
            status=entity.status,
            messages=[MessageDocument.from_entity(msg) for msg in entity.messages] if entity.messages else [],
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
