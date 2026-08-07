from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

DOCUMENT_STATUS = Literal["processing", "active", "error"]


class DocumentMetadataSchema(BaseModel):
    source_type: str = Field(default="manual")
    source_uri: str | None = None
    mime_type: str | None = None
    language: str = Field(default="en")
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DocumentVersionSchema(BaseModel):
    version_number: int = Field(..., ge=1)
    checksum: str | None = None
    created_by: str | None = None
    notes: str | None = None
    is_current: bool = False
    created_at: datetime | None = None


class KnowledgeChunkCreateSchema(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0)
    title: str | None = None
    content: str
    embedding_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkUpdateSchema(BaseModel):
    version_number: int | None = Field(default=None, ge=1)
    chunk_index: int | None = Field(default=None, ge=0)
    title: str | None = None
    content: str | None = None
    embedding_id: str | None = None
    metadata: dict[str, Any] | None = None


class KnowledgeChunkResponseSchema(BaseModel):
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


class KnowledgeDocumentCreateSchema(BaseModel):
    store_id: str
    title: str
    description: str | None = None
    source_url: str | None = None
    status: DOCUMENT_STATUS = "processing"
    language: str = Field(default="en")
    metadata: DocumentMetadataSchema = Field(default_factory=DocumentMetadataSchema)
    versions: list[DocumentVersionSchema] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunking_strategy: str = Field(default="manual")


class KnowledgeDocumentUpdateSchema(BaseModel):
    store_id: str | None = None
    title: str | None = None
    description: str | None = None
    source_url: str | None = None
    status: DOCUMENT_STATUS | None = None
    language: str | None = None
    metadata: DocumentMetadataSchema | None = None
    versions: list[DocumentVersionSchema] | None = None
    current_version: int | None = Field(default=None, ge=1)
    chunking_strategy: str | None = None


class KnowledgeDocumentResponseSchema(BaseModel):
    id: str
    store_id: str
    title: str
    description: str | None = None
    source_url: str | None = None
    status: str
    language: str
    metadata: DocumentMetadataSchema
    versions: list[DocumentVersionSchema]
    current_version: int
    chunks: list[KnowledgeChunkResponseSchema] = Field(default_factory=list)
    chunking_strategy: str
    processed_text: str | None = None
    page_count: int | None = None
    word_count: int | None = None
    char_count: int | None = None
    estimated_tokens: int | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class BusinessSummaryCreateSchema(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    title: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessSummaryUpdateSchema(BaseModel):
    version_number: int | None = Field(default=None, ge=1)
    title: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] | None = None


class BusinessSummaryResponseSchema(BaseModel):
    id: str
    document_id: str
    version_number: int
    title: str
    summary: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PaginatedKnowledgeDocumentResponseSchema(BaseModel):
    items: list[KnowledgeDocumentResponseSchema]
    total: int
    page: int
    page_size: int


class PaginatedKnowledgeChunkResponseSchema(BaseModel):
    items: list[KnowledgeChunkResponseSchema]
    total: int
    page: int
    page_size: int


class PaginatedBusinessSummaryResponseSchema(BaseModel):
    items: list[BusinessSummaryResponseSchema]
    total: int
    page: int
    page_size: int


class DeleteResponseSchema(BaseModel):
    success: bool


class UploadResponseSchema(BaseModel):
    id: str
    original_filename: str
    stored_filename: str
    file_path: str
    file_size: int
    mime_type: str
    extension: str
    checksum: str
    content_type: str
    uploaded_by: str
    organization_id: str
    store_id: str
    knowledge_scope: str
    status: str
    document_metadata: DocumentMetadataSchema
    virus_scan_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    document_id: str | None = None
    already_uploaded: bool = False


class PaginatedUploadResponseSchema(BaseModel):
    items: list[UploadResponseSchema]
    total: int
    page: int
    page_size: int
