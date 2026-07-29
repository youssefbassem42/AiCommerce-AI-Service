from datetime import UTC, datetime
from typing import Any

from pydantic import Field

from app.shared.kernel.entity import Entity


class BusinessSummary(Entity[str]):
    """Domain representation of a stored business summary for a document version."""

    document_id: str = Field(..., description="Parent document identifier")
    version_number: int = Field(default=1, ge=1)
    title: str = Field(..., description="Summary title")
    summary: str = Field(..., description="Summary body")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
