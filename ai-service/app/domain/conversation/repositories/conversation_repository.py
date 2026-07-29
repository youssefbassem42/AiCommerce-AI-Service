from abc import ABC, abstractmethod
from typing import List, Optional
from app.shared.kernel.repository import AsyncRepository
from app.domain.conversation.entities.conversation import Conversation
from app.domain.conversation.entities.message import Message

class ConversationRepository(AsyncRepository[Conversation, str], ABC):
    """Domain repository interface for Conversation Aggregate."""

    @abstractmethod
    async def find_by_customer_id(self, customer_id: str, limit: int = 20, skip: int = 0) -> List[Conversation]:
        """Find conversations for a specific customer."""
        pass

    @abstractmethod
    async def add_message_to_conversation(self, conversation_id: str, message: Message) -> bool:
        """Atomically append a message to a conversation."""
        pass
