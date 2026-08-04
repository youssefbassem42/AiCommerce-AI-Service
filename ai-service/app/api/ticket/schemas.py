from datetime import datetime

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
    line_items: list[LineItemSchema] = Field(default_factory=list)


class CustomerProfileSchema(BaseModel):
    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class ConversationSummarySchema(BaseModel):
    message_count: int
    last_message_at: datetime | None = None
    recent_messages: list[str] = Field(default_factory=list)


class TicketCreateSchema(BaseModel):
    store_id: str
    customer_id: str
    conversation_id: str | None = None
    messages: list[str] = Field(default_factory=list, max_length=50)


class TicketMessageSchema(BaseModel):
    id: str
    sender: str
    content: str
    created_at: datetime


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
    resolution_type: str = "unresolved"
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime
    customer: CustomerProfileSchema | None = None
    recent_orders: list[OrderSchema] = Field(default_factory=list)
    conversation: ConversationSummarySchema | None = None
    messages: list[TicketMessageSchema] = Field(default_factory=list)
    assigned_to: str | None = None
    eta: datetime | None = None


class TicketListResponseSchema(BaseModel):
    items: list[TicketResponseSchema]
    total: int
    page: int
    page_size: int


class TicketStatusUpdateSchema(BaseModel):
    status: str = Field(..., pattern=r"^(open|in_progress|resolved|closed)$")
    resolution_type: str | None = Field(default=None, pattern=r"^(ai|human|unresolved|escalated)$")


class AddMessageSchema(BaseModel):
    sender: str = Field(default="customer", pattern=r"^(customer|agent|system)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ResolveTicketSchema(BaseModel):
    resolution_type: str = Field(default="human", pattern=r"^(ai|human)$")
    message: str | None = Field(default=None, max_length=4000)


class EscalateTicketSchema(BaseModel):
    priority: str | None = Field(default=None, pattern=r"^(low|medium|high|urgent|p1|p2|p3|p4)$")
    assigned_to: str | None = Field(default=None, max_length=200)
    eta: datetime | None = None
    message: str | None = Field(default=None, max_length=4000)


class TicketNotificationSchema(BaseModel):
    id: str
    ticket_id: str
    store_id: str
    customer_id: str
    message: str
    eta: datetime | None = None
    read: bool = False
    created_at: datetime


class TicketNotificationListSchema(BaseModel):
    items: list[TicketNotificationSchema]
    total: int
    unread: int


class DeleteResponseSchema(BaseModel):
    success: bool


class ResolutionMetricsResponseSchema(BaseModel):
    store_id: str
    total_tickets: int
    ai_resolved: int
    human_resolved: int
    unresolved: int
    escalated: int
    resolution_rate: float
