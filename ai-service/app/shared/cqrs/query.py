from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class Query(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = Field(default=None)
