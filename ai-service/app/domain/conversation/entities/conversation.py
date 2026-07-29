from datetime import UTC, datetime

from pydantic import Field

from app.domain.conversation.entities.message import Message
from app.shared.kernel.aggregate_root import AggregateRoot


class Conversation(AggregateRoot[str]):
    """Domain Aggregate Root representing a conversation."""

    customer_id: str = Field(..., description="ID of the customer participating in the conversation")
    store_id: str = Field(..., description="ID of the commerce store context")
    status: str = Field(default="active", description="Conversation status (active, ended, archived)")
    messages: list[Message] = Field(default_factory=list, description="List of messages in this conversation")
    summary: str | None = Field(None, description="Summary of the conversation")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = Field(None, description="Time when the conversation ended")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation and update the updated_at timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.now(UTC)
