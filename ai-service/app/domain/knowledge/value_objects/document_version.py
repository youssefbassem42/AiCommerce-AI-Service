from datetime import UTC, datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentVersion(BaseModel):
    """Represents a stored version of a knowledge document."""

    version_number: int = Field(..., ge=1)
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    is_current: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
