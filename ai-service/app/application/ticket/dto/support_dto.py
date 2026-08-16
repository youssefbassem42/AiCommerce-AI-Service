from datetime import datetime

from pydantic import BaseModel, Field


class SupportResponse(BaseModel):
    query: str
    store_id: str
    customer_id: str | None = None
    verified: bool = False
    issue_category: str | None = None
    resolution_steps: list[str] = Field(default_factory=list)
    escalation_needed: bool = False
    escalation_reason: str | None = None
    ticket_id: str | None = None
    priority: str | None = None
    assigned_to: str | None = None
    eta: datetime | None = None
    rationale: str | None = None
    latency_ms: float = 0.0
    error: str | None = Field(default=None, description="Non-fatal error encountered during support flow")
    products: list[dict] = Field(
        default_factory=list,
        description="Product cards matched for product-information inquiries",
    )
