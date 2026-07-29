from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


class DocumentMetadataDTO(BaseModel):
    source_type: str = Field(default="manual")
    source_uri: Optional[str] = None
    mime_type: Optional[str] = None
    language: str = Field(default="en")
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DocumentVersionDTO(BaseModel):
    version_number: int = Field(..., ge=1)
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    is_current: bool = False
    created_at: Optional[datetime] = None


class KnowledgeChunkCreateDTO(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0)
    title: Optional[str] = None
    content: str
    embedding_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkUpdateDTO(BaseModel):
    version_number: Optional[int] = Field(default=None, ge=1)
    chunk_index: Optional[int] = Field(default=None, ge=0)
    title: Optional[str] = None
    content: Optional[str] = None
    embedding_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class KnowledgeChunkDTO(BaseModel):
    id: str
    document_id: str
    version_number: int
    chunk_index: int
    title: Optional[str] = None
    content: str
    embedding_id: Optional[str] = None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentCreateDTO(BaseModel):
    store_id: str
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: str = Field(default="draft")
    language: str = Field(default="en")
    metadata: DocumentMetadataDTO = Field(default_factory=DocumentMetadataDTO)
    versions: list[DocumentVersionDTO] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunking_strategy: str = Field(default="manual")


class KnowledgeDocumentUpdateDTO(BaseModel):
    store_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[DocumentMetadataDTO] = None
    versions: Optional[list[DocumentVersionDTO]] = None
    current_version: Optional[int] = Field(default=None, ge=1)
    chunking_strategy: Optional[str] = None


class KnowledgeDocumentDTO(BaseModel):
    id: str
    store_id: str
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: str
    language: str
    metadata: DocumentMetadataDTO
    versions: list[DocumentVersionDTO]
    current_version: int
    chunks: list[KnowledgeChunkDTO] = Field(default_factory=list)
    chunking_strategy: str
    processed_text: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    estimated_tokens: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class BusinessSummaryCreateDTO(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    title: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessSummaryUpdateDTO(BaseModel):
    version_number: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = None
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


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


class PaginatedResultDTO(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
