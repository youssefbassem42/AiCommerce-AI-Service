from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeVersionInfo(BaseModel):
    organization_id: str = Field(..., description="Organization scope")
    store_id: str = Field(..., description="Store scope")
    version_number: int = Field(..., ge=1, description="Monotonic knowledge version")
    previous_version: int = Field(default=0, description="Previous version for rollback")
    status: str = Field(default="active", description="active | previous | rolled_back")
    document_count: int = Field(default=0, description="Documents in this version")
    chunk_count: int = Field(default=0, description="Chunks in this version")
    files_processed: int = Field(default=0, description="Files processed this sync")
    files_skipped: int = Field(default=0, description="Unchanged files skipped")
    total_files: int = Field(default=0, description="Total files considered")
    summary_generated: bool = Field(default=False, description="Business summary completed")
    embeddings_generated: bool = Field(default=False, description="Embeddings completed")
    vectors_synced: bool = Field(default=False, description="Vector DB synced")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)
