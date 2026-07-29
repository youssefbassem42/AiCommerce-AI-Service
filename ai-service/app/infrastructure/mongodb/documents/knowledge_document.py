from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class DocumentMetadataModel(BaseModel):
    source_type: str = Field(default="manual")
    source_uri: Optional[str] = None
    mime_type: Optional[str] = None
    language: str = Field(default="en")
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_value_object(self) -> DocumentMetadata:
        return DocumentMetadata(**self.model_dump())

    @classmethod
    def from_value_object(cls, value: DocumentMetadata) -> "DocumentMetadataModel":
        return cls(**value.model_dump())


class DocumentVersionModel(BaseModel):
    version_number: int = Field(..., ge=1)
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    is_current: bool = False
    created_at: Any

    def to_value_object(self) -> DocumentVersion:
        return DocumentVersion(**self.model_dump())

    @classmethod
    def from_value_object(cls, value: DocumentVersion) -> "DocumentVersionModel":
        return cls(**value.model_dump())


class KnowledgeDocumentModel(BaseMongoDocument):
    """MongoDB document model representing a KnowledgeDocument."""

    store_id: str = Field(..., index=True)
    title: str = Field(...)
    description: Optional[str] = None
    source_url: Optional[str] = Field(None)
    status: str = Field(default="draft", index=True)
    language: str = Field(default="en")
    metadata: DocumentMetadataModel = Field(default_factory=DocumentMetadataModel)
    versions: list[DocumentVersionModel] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunking_strategy: str = Field(default="manual")
    processed_text: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    estimated_tokens: Optional[int] = None

    def to_entity(self) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=str(self.id),
            store_id=self.store_id,
            title=self.title,
            description=self.description,
            source_url=self.source_url,
            status=self.status,
            language=self.language,
            metadata=self.metadata.to_value_object(),
            versions=[version.to_value_object() for version in self.versions],
            current_version=self.current_version,
            chunking_strategy=self.chunking_strategy,
            processed_text=self.processed_text,
            page_count=self.page_count,
            word_count=self.word_count,
            char_count=self.char_count,
            estimated_tokens=self.estimated_tokens,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: KnowledgeDocument) -> "KnowledgeDocumentModel":
        return cls(
            _id=entity.id,
            store_id=entity.store_id,
            title=entity.title,
            description=entity.description,
            source_url=entity.source_url,
            status=entity.status,
            language=entity.language,
            metadata=DocumentMetadataModel.from_value_object(entity.metadata),
            versions=[DocumentVersionModel.from_value_object(v) for v in entity.versions],
            current_version=entity.current_version,
            chunking_strategy=entity.chunking_strategy,
            processed_text=entity.processed_text,
            page_count=entity.page_count,
            word_count=entity.word_count,
            char_count=entity.char_count,
            estimated_tokens=entity.estimated_tokens,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
