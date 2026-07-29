from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentMetadataSchema(BaseModel):
    source_type: str = Field(default="manual")
    source_uri: Optional[str] = None
    mime_type: Optional[str] = None
    language: str = Field(default="en")
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class DocumentVersionSchema(BaseModel):
    version_number: int = Field(..., ge=1)
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    is_current: bool = False
    created_at: Optional[datetime] = None


class KnowledgeChunkCreateSchema(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(..., ge=0)
    title: Optional[str] = None
    content: str
    embedding_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunkUpdateSchema(BaseModel):
    version_number: Optional[int] = Field(default=None, ge=1)
    chunk_index: Optional[int] = Field(default=None, ge=0)
    title: Optional[str] = None
    content: Optional[str] = None
    embedding_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class KnowledgeChunkResponseSchema(BaseModel):
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


class KnowledgeDocumentCreateSchema(BaseModel):
    store_id: str
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: str = Field(default="draft")
    language: str = Field(default="en")
    metadata: DocumentMetadataSchema = Field(default_factory=DocumentMetadataSchema)
    versions: list[DocumentVersionSchema] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunking_strategy: str = Field(default="manual")


class KnowledgeDocumentUpdateSchema(BaseModel):
    store_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[DocumentMetadataSchema] = None
    versions: Optional[list[DocumentVersionSchema]] = None
    current_version: Optional[int] = Field(default=None, ge=1)
    chunking_strategy: Optional[str] = None


class KnowledgeDocumentResponseSchema(BaseModel):
    id: str
    store_id: str
    title: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    status: str
    language: str
    metadata: DocumentMetadataSchema
    versions: list[DocumentVersionSchema]
    current_version: int
    chunks: list[KnowledgeChunkResponseSchema] = Field(default_factory=list)
    chunking_strategy: str
    processed_text: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    char_count: Optional[int] = None
    estimated_tokens: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class BusinessSummaryCreateSchema(BaseModel):
    document_id: str
    version_number: int = Field(default=1, ge=1)
    title: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessSummaryUpdateSchema(BaseModel):
    version_number: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = None
    summary: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


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
    deleted_at: Optional[datetime] = None


class PaginatedUploadResponseSchema(BaseModel):
    items: list[UploadResponseSchema]
    total: int
    page: int
    page_size: int
