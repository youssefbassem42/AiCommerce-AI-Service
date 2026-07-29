from datetime import datetime, UTC
from uuid import uuid4
from pydantic import BaseModel, Field

class DomainEvent(BaseModel):
    """Base class for Domain Events."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
