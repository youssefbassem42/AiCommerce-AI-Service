from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.shared.kernel.aggregate_root import AggregateRoot

RESOLUTION_TYPES = {"ai", "human", "unresolved", "escalated"}

MESSAGE_SENDERS = {"customer", "agent", "system"}


class TicketMessage(BaseModel):
    """Value object representing a single message in a ticket thread."""

    id: str = Field(..., description="Message ID")
    sender: str = Field(..., description="Sender of the message (customer, agent, system)")
    content: str = Field(..., description="Message body")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TicketAnalysis(AggregateRoot[str]):
    """Domain Aggregate Root representing an AI-based customer support ticket analysis."""

    ticket_id: str = Field(..., description="External or database ID of the customer support ticket")
    store_id: str = Field(..., description="Commerce store context ID")
    customer_id: str = Field(..., description="ID of the customer who created the ticket")
    sentiment: str = Field(..., description="Calculated sentiment of the ticket (positive, neutral, negative)")
    category: str = Field(..., description="Identified category (e.g. billing, shipping, product_quality)")
    summary: str = Field(..., description="Brief summary of the ticket content")
    priority: str = Field(..., description="Calculated urgency priority (low, medium, high, urgent)")
    status: str = Field(default="open", description="Ticket status (open, in_progress, resolved, closed)")
    suggested_response: str = Field(..., description="AI suggested answer draft")
    resolution_type: str = Field(
        default="unresolved", description="How the ticket was resolved (ai, human, unresolved, escalated)"
    )
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    messages: list[TicketMessage] = Field(default_factory=list, description="Ticket thread messages")
    assigned_to: str | None = Field(default=None, description="Human agent/team the ticket is assigned to")
    eta: datetime | None = Field(default=None, description="Expected resolution time communicated to the customer")
