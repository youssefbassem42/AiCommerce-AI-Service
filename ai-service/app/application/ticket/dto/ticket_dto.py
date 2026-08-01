from datetime import datetime

from pydantic import BaseModel, Field


class LineItemDTO(BaseModel):
    title: str
    quantity: int
    price: float


class OrderDTO(BaseModel):
    id: str
    total_price: float
    currency: str
    financial_status: str
    created_at: datetime
    line_items: list[LineItemDTO] = Field(default_factory=list)


class CustomerProfileDTO(BaseModel):
    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class ConversationSummaryDTO(BaseModel):
    message_count: int
    last_message_at: datetime | None = None
    recent_messages: list[str] = Field(default_factory=list)


class TicketCreateDTO(BaseModel):
    store_id: str
    customer_id: str
    conversation_id: str | None = None
    messages: list[str] = Field(default_factory=list, description="Conversation messages to analyze")


class TicketStatusUpdateDTO(BaseModel):
    status: str
    resolution_type: str | None = None


class TicketMessageDTO(BaseModel):
    id: str
    sender: str
    content: str
    created_at: datetime


class TicketDTO(BaseModel):
    id: str
    ticket_id: str
    store_id: str
    customer_id: str
    sentiment: str
    category: str
    summary: str
    priority: str
    status: str
    suggested_response: str
    resolution_type: str = "unresolved"
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime

    customer: CustomerProfileDTO | None = None
    recent_orders: list[OrderDTO] = Field(default_factory=list)
    conversation: ConversationSummaryDTO | None = None
    messages: list[TicketMessageDTO] = Field(default_factory=list)
    assigned_to: str | None = None
    eta: datetime | None = None


class ResolutionMetricsDTO(BaseModel):
    store_id: str
    total_tickets: int
    ai_resolved: int
    human_resolved: int
    unresolved: int
    escalated: int
    resolution_rate: float
