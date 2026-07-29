from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LineItemSchema(BaseModel):
    title: str
    quantity: int
    price: float


class OrderSchema(BaseModel):
    id: str
    total_price: float
    currency: str
    financial_status: str
    created_at: datetime
    line_items: List[LineItemSchema] = Field(default_factory=list)


class CustomerProfileSchema(BaseModel):
    id: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class ConversationSummarySchema(BaseModel):
    message_count: int
    last_message_at: Optional[datetime] = None
    recent_messages: List[str] = Field(default_factory=list)


class TicketCreateSchema(BaseModel):
    store_id: str
    customer_id: str
    conversation_id: Optional[str] = None
    messages: List[str] = Field(default_factory=list, max_length=50)


class TicketResponseSchema(BaseModel):
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
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime
    customer: Optional[CustomerProfileSchema] = None
    recent_orders: List[OrderSchema] = Field(default_factory=list)
    conversation: Optional[ConversationSummarySchema] = None


class TicketListResponseSchema(BaseModel):
    items: List[TicketResponseSchema]
    total: int
    page: int
    page_size: int


class TicketStatusUpdateSchema(BaseModel):
    status: str = Field(..., pattern=r"^(open|in_progress|resolved|closed)$")


class DeleteResponseSchema(BaseModel):
    success: bool
