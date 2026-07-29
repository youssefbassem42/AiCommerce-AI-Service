from datetime import datetime, UTC
from pydantic import Field
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.domain.ticket.entities.ticket_analysis import TicketAnalysis

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
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

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
            analyzed_at=self.analyzed_at
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
            analyzed_at=entity.analyzed_at
        )
