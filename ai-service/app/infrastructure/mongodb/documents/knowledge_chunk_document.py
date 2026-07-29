from typing import Any, Optional

from pydantic import Field

from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class KnowledgeChunkDocument(BaseMongoDocument):
    """MongoDB document model representing a KnowledgeChunk."""

    document_id: str = Field(..., index=True)
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0)
    title: Optional[str] = None
    content: str = Field(...)
    embedding_id: Optional[str] = Field(None, index=True)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_entity(self) -> KnowledgeChunk:
        return KnowledgeChunk(
            id=str(self.id),
            document_id=self.document_id,
            version_number=self.version_number,
            chunk_index=self.chunk_index,
            title=self.title,
            content=self.content,
            embedding_id=self.embedding_id,
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: KnowledgeChunk) -> "KnowledgeChunkDocument":
        return cls(
            _id=entity.id,
            document_id=entity.document_id,
            version_number=entity.version_number,
            chunk_index=entity.chunk_index,
            title=entity.title,
            content=entity.content,
            embedding_id=entity.embedding_id,
            metadata=entity.metadata,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
