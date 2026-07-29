from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field

from app.domain.knowledge.value_objects.knowledge_version import KnowledgeVersionInfo
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class KnowledgeVersionDocument(BaseMongoDocument):
    organization_id: str = Field(..., index=True)
    store_id: str = Field(..., index=True)
    version_number: int = Field(..., ge=1)
    previous_version: int = Field(default=0)
    status: str = Field(default="active", index=True)
    document_count: int = Field(default=0)
    chunk_count: int = Field(default=0)
    files_processed: int = Field(default=0)
    files_skipped: int = Field(default=0)
    total_files: int = Field(default=0)
    summary_generated: bool = Field(default=False)
    embeddings_generated: bool = Field(default=False)
    vectors_synced: bool = Field(default=False)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = Field(default=None)
    error: Optional[str] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_value_object(self) -> KnowledgeVersionInfo:
        return KnowledgeVersionInfo(
            organization_id=self.organization_id,
            store_id=self.store_id,
            version_number=self.version_number,
            previous_version=self.previous_version,
            status=self.status,
            document_count=self.document_count,
            chunk_count=self.chunk_count,
            files_processed=self.files_processed,
            files_skipped=self.files_skipped,
            total_files=self.total_files,
            summary_generated=self.summary_generated,
            embeddings_generated=self.embeddings_generated,
            vectors_synced=self.vectors_synced,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            metadata=self.metadata,
        )

    @classmethod
    def from_value_object(cls, vo: KnowledgeVersionInfo) -> "KnowledgeVersionDocument":
        return cls(
            _id=cls._generate_id(vo),
            organization_id=vo.organization_id,
            store_id=vo.store_id,
            version_number=vo.version_number,
            previous_version=vo.previous_version,
            status=vo.status,
            document_count=vo.document_count,
            chunk_count=vo.chunk_count,
            files_processed=vo.files_processed,
            files_skipped=vo.files_skipped,
            total_files=vo.total_files,
            summary_generated=vo.summary_generated,
            embeddings_generated=vo.embeddings_generated,
            vectors_synced=vo.vectors_synced,
            started_at=vo.started_at,
            completed_at=vo.completed_at,
            error=vo.error,
            metadata=vo.metadata,
        )

    @staticmethod
    def _generate_id(vo: KnowledgeVersionInfo) -> str:
        import hashlib
        raw = f"{vo.organization_id}:{vo.store_id}:v{vo.version_number}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]
