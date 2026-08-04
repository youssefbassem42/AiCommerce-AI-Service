from datetime import datetime

from pydantic import BaseModel, Field


class EscalationResponse(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    ticket_id: str | None = None
    category: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    eta: datetime | None = None
    summary: str | None = None
    notification_message: str | None = None
    rationale: str | None = None
    latency_ms: float = 0.0
    error: str | None = Field(default=None, description="Non-fatal error encountered during escalation")
