from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.application.knowledge.dto.knowledge_dto import DocumentMetadataDTO


class UploadCreateDTO(BaseModel):
    """DTO for initiating a file upload."""

    original_filename: str
    file_size: int = Field(..., ge=0)
    mime_type: str
    extension: str
    checksum: str
    uploaded_by: str
    organization_id: str
    store_id: str
    knowledge_scope: str = Field(default="general")
    document_metadata: DocumentMetadataDTO = Field(default_factory=DocumentMetadataDTO)
    content_type: str = "document"


class UploadDTO(BaseModel):
    """DTO representing a completed document upload."""

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
    document_metadata: DocumentMetadataDTO
    virus_scan_status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
