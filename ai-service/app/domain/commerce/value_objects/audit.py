from datetime import datetime, UTC
from typing import Optional

from pydantic import BaseModel, Field


class AuditInfo(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by: Optional[str] = None
