from datetime import datetime, UTC
from typing import List, Optional
from pydantic import Field
from app.shared.kernel.aggregate_root import AggregateRoot
from app.domain.conversation.entities.message import Message

class Conversation(AggregateRoot[str]):
    """Domain Aggregate Root representing a conversation."""
    customer_id: str = Field(..., description="ID of the customer participating in the conversation")
    store_id: str = Field(..., description="ID of the commerce store context")
    status: str = Field(default="active", description="Conversation status (active, ended, archived)")
    messages: List[Message] = Field(default_factory=list, description="List of messages in this conversation")
    summary: Optional[str] = Field(None, description="Summary of the conversation")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: Optional[datetime] = Field(None, description="Time when the conversation ended")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation and update the updated_at timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.now(UTC)
