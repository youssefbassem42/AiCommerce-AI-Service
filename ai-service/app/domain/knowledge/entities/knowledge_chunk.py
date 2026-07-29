from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field

from app.shared.kernel.entity import Entity


class KnowledgeChunk(Entity[str]):
    """Domain representation of a persisted knowledge document chunk."""

    document_id: str = Field(..., description="ID of the parent KnowledgeDocument")
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0, description="Sequential chunk index")
    title: Optional[str] = Field(default=None, description="Optional chunk title")
    content: str = Field(..., description="Text content of this chunk")
    embedding_id: Optional[str] = Field(
        default=None,
        description="Reserved field for future vector linkage",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary metadata for filtering",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
