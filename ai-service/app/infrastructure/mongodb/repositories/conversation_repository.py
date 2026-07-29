from typing import List, Optional, Any
from datetime import datetime, UTC
from bson import ObjectId
import logging

from app.domain.conversation.entities.conversation import Conversation
from app.domain.conversation.entities.message import Message
from app.domain.conversation.repositories.conversation_repository import ConversationRepository as IConversationRepository
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.conversation_document import ConversationDocument
from app.infrastructure.mongodb.documents.message_document import MessageDocument
from app.infrastructure.mongodb.collections import get_conversations_collection, get_messages_collection

logger = logging.getLogger(__name__)

class ConversationRepository(BaseMongoRepository[ConversationDocument, Conversation], IConversationRepository):
    """MongoDB implementation of the ConversationRepository with transaction and session support."""

    def __init__(self):
        super().__init__(get_conversations_collection(), ConversationDocument)
        self.messages_collection = get_messages_collection()

    async def create(self, entity: Conversation, session: Any = None) -> Conversation:
        """Create a new conversation along with its messages atomically."""
        try:
            await super().create(entity, session=session)
            if entity.messages:
                msg_docs = [MessageDocument.from_entity(m).to_mongo_dict() for m in entity.messages]
                await self.messages_collection.insert_many(msg_docs, session=session)
            return entity
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def update(self, entity: Conversation, session: Any = None) -> Conversation:
        """Update an existing conversation and sync messages atomically."""
        try:
            await super().update(entity, session=session)
            await self.messages_collection.delete_many({"conversation_id": entity.id}, session=session)
            if entity.messages:
                msg_docs = [MessageDocument.from_entity(m).to_mongo_dict() for m in entity.messages]
                await self.messages_collection.insert_many(msg_docs, session=session)
            return entity
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_by_id(self, id: str, session: Any = None) -> Optional[Conversation]:
        """Find a conversation by ID and populate its messages."""
        try:
            conversation = await super().find_by_id(id, session=session)
            if not conversation:
                return None
            
            cursor = self.messages_collection.find(
                {"conversation_id": id}, 
                session=session
            ).sort("timestamp", 1)
            
            messages = []
            async for data in cursor:
                doc = MessageDocument.from_mongo_dict(data)
                messages.append(doc.to_entity())
            conversation.messages = messages
            return conversation
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_by_customer_id(
        self, customer_id: str, limit: int = 20, skip: int = 0, session: Any = None
    ) -> List[Conversation]:
        """Retrieve conversations of a customer with their messages populated."""
        try:
            conversations = await self.find_many(
                {"customer_id": customer_id}, 
                limit=limit, 
                skip=skip, 
                session=session
            )
            for conv in conversations:
                cursor = self.messages_collection.find(
                    {"conversation_id": conv.id}, 
                    session=session
                ).sort("timestamp", 1)
                
                messages = []
                async for data in cursor:
                    doc = MessageDocument.from_mongo_dict(data)
                    messages.append(doc.to_entity())
                conv.messages = messages
            return conversations
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def add_message_to_conversation(
        self, conversation_id: str, message: Message, session: Any = None
    ) -> bool:
        """Atomically append a message to the conversation and update the conversation timestamp."""
        try:
            doc = MessageDocument.from_entity(message)
            await self.messages_collection.insert_one(doc.to_mongo_dict(), session=session)
            
            result = await self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {"updated_at": datetime.now(UTC)}},
                session=session
            )
            return result.modified_count > 0
        except Exception as e:
            self._handle_db_error(e)
            raise
