from datetime import datetime
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field

DOCUMENT_STATUS = Literal["processing", "active", "error"]


class DocumentMetadataDTO(BaseModel):
    source_type: str = Field(default="manual")
    source_uri: str | None = None
    mime_type: str | None = None
    language: str = Field(default="en")
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DocumentVersionDTO(BaseModel):
    version_number: int = Field(..., ge=1)
    checksum: str | None = None
    created_by: str | None = None
    notes: str | None = None
    is_current: bool = False
    created_at: datetime | None = None


class KnowledgeChunkCreateDTO(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0)
    title: str | None = None
    content: str
    embedding_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkUpdateDTO(BaseModel):
    version_number: int | None = Field(default=None, ge=1)
    chunk_index: int | None = Field(default=None, ge=0)
    title: str | None = None
    content: str | None = None
    embedding_id: str | None = None
    metadata: dict[str, Any] | None = None


class KnowledgeChunkDTO(BaseModel):
    id: str
    document_id: str
    version_number: int
    chunk_index: int
    title: str | None = None
    content: str
    embedding_id: str | None = None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreateDTO(BaseModel):
    store_id: str
    title: str
    description: str | None = None
    source_url: str | None = None
    status: DOCUMENT_STATUS = "processing"
    language: str = Field(default="en")
    metadata: DocumentMetadataDTO = Field(default_factory=DocumentMetadataDTO)
    versions: list[DocumentVersionDTO] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunking_strategy: str = Field(default="manual")


class KnowledgeDocumentUpdateDTO(BaseModel):
    store_id: str | None = None
    title: str | None = None
    description: str | None = None
    source_url: str | None = None
    status: str | None = None
    language: str | None = None
    metadata: DocumentMetadataDTO | None = None
    versions: list[DocumentVersionDTO] | None = None
    current_version: int | None = Field(default=None, ge=1)
    chunking_strategy: str | None = None


class KnowledgeDocumentDTO(BaseModel):
    id: str
    store_id: str
    title: str
    description: str | None = None
    source_url: str | None = None
    status: str
    language: str
    metadata: DocumentMetadataDTO
    versions: list[DocumentVersionDTO]
    current_version: int
    chunks: list[KnowledgeChunkDTO] = Field(default_factory=list)
    chunking_strategy: str
    processed_text: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    char_count: int | None = None
    estimated_tokens: int | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class BusinessSummaryCreateDTO(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    title: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessSummaryUpdateDTO(BaseModel):
    version_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] | None = None


class BusinessSummaryDTO(BaseModel):
    id: str
    document_id: str
    version_number: int
    title: str
    summary: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class PaginatedResultDTO[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
