from datetime import UTC, datetime

from pydantic import Field

from app.domain.ticket.entities.ticket_analysis import TicketAnalysis, TicketMessage
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class TicketAnalysisDocument(BaseMongoDocument):
    """MongoDB document model representing a TicketAnalysis."""

    ticket_id: str = Field(..., index=True)
    store_id: str = Field(..., index=True)
    customer_id: str = Field(..., index=True)
    sentiment: str = Field(...)
    category: str = Field(...)
    summary: str = Field(...)
    priority: str = Field(...)
    status: str = Field(default="open")
    suggested_response: str = Field(...)
    resolution_type: str = Field(default="unresolved")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    messages: list[dict] = Field(default_factory=list)
    assigned_to: str | None = Field(default=None)
    eta: datetime | None = Field(default=None)
    conversation_id: str | None = Field(default=None)

    def to_entity(self) -> TicketAnalysis:
        """Map document to domain Entity."""
        return TicketAnalysis(
            id=str(self.id),
            ticket_id=self.ticket_id,
            store_id=self.store_id,
            customer_id=self.customer_id,
            sentiment=self.sentiment,
            category=self.category,
            summary=self.summary,
            priority=self.priority,
            status=self.status,
            suggested_response=self.suggested_response,
            resolution_type=self.resolution_type,
            analyzed_at=self.analyzed_at,
            messages=[TicketMessage(**msg) for msg in (self.messages or [])],
            assigned_to=self.assigned_to,
            eta=self.eta,
            conversation_id=self.conversation_id,
        )

    @classmethod
    def from_entity(cls, entity: TicketAnalysis) -> "TicketAnalysisDocument":
        """Map domain Entity to MongoDB Document."""
        return cls(
            ticket_id=entity.ticket_id,
            store_id=entity.store_id,
            customer_id=entity.customer_id,
            sentiment=entity.sentiment,
            category=entity.category,
            summary=entity.summary,
            priority=entity.priority,
            status=entity.status,
            suggested_response=entity.suggested_response,
            resolution_type=entity.resolution_type,
            analyzed_at=entity.analyzed_at,
            messages=[msg.model_dump(mode="json") for msg in entity.messages],
            assigned_to=entity.assigned_to,
            eta=entity.eta,
            conversation_id=entity.conversation_id,
        )
