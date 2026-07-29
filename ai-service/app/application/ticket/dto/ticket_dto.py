from datetime import datetime
from typing import Any, Dict, List, Optional
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
    line_items: List[LineItemDTO] = Field(default_factory=list)


class CustomerProfileDTO(BaseModel):
    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class ConversationSummaryDTO(BaseModel):
    message_count: int
    last_message_at: Optional[datetime] = None
    recent_messages: List[str] = Field(default_factory=list)


class TicketCreateDTO(BaseModel):
    store_id: str
    customer_id: str
    conversation_id: Optional[str] = None
    messages: List[str] = Field(default_factory=list, description="Conversation messages to analyze")


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

    customer: Optional[CustomerProfileDTO] = None
    recent_orders: List[OrderDTO] = Field(default_factory=list)
    conversation: Optional[ConversationSummaryDTO] = None


class TicketStatusUpdateDTO(BaseModel):
    status: str
    resolution_type: Optional[str] = None


class ResolutionMetricsDTO(BaseModel):
    store_id: str
    total_tickets: int
    ai_resolved: int
    human_resolved: int
    unresolved: int
    escalated: int
    resolution_rate: float
