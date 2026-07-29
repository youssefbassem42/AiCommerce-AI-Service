from app.domain.conversation.entities.conversation import Conversation
from app.domain.conversation.entities.message import Message
from app.infrastructure.mongodb.documents.conversation_document import ConversationDocument
from app.infrastructure.mongodb.documents.message_document import MessageDocument
from app.application.conversation.dto.conversation_dto import ConversationDTO, MessageDTO

class ConversationMapper:
    """Maps Conversation Aggregate between Mongo Documents, Domain Entities, and DTOs."""

    @staticmethod
    def to_entity(doc: ConversationDocument) -> Conversation:
        """Map Mongo Document to Domain Entity."""
        return doc.to_entity()

    @staticmethod
    def to_document(entity: Conversation) -> ConversationDocument:
        """Map Domain Entity to Mongo Document."""
        return ConversationDocument.from_entity(entity)

    @staticmethod
    def to_dto(entity: Conversation) -> ConversationDTO:
        """Map Domain Entity to DTO."""
        return ConversationDTO(
            id=entity.id,
            customer_id=entity.customer_id,
            store_id=entity.store_id,
            status=entity.status,
            messages=[
                MessageDTO(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    role=msg.role,
                    content=msg.content,
                    sender=msg.sender,
                    sentiment=msg.sentiment,
                    intent=msg.intent,
                    timestamp=msg.timestamp,
                    metadata=msg.metadata
                )
                for msg in entity.messages
            ],
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
