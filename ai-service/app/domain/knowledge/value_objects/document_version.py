from datetime import UTC, datetime

from pydantic import BaseModel, Field


class DocumentVersion(BaseModel):
    """Represents a stored version of a knowledge document."""

    version_number: int = Field(..., ge=1)
    checksum: str | None = None
    created_by: str | None = None
    notes: str | None = None
    is_current: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
