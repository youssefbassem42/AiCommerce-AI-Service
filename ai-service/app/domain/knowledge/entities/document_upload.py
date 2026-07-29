from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import Field, field_validator

from app.domain.knowledge.value_objects.document_metadata import DocumentMetadata
from app.shared.kernel.entity import Entity


ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt", ".csv"}
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/csv",
}


class DocumentUpload(Entity[str]):
    """Domain entity representing a file uploaded to the knowledge base."""

    original_filename: str = Field(..., description="Original file name")
    stored_filename: str = Field(..., description="Unique stored file name")
    file_path: str = Field(..., description="Path in storage backend")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="Detected MIME type")
    extension: str = Field(..., description="File extension")
    checksum: str = Field(..., description="SHA-256 checksum")
    content_type: str = Field(..., description="Upload content type label")
    uploaded_by: str = Field(..., description="User who uploaded the file")
    organization_id: str = Field(..., description="Organization scope")
    store_id: str = Field(..., description="Store scope")
    knowledge_scope: str = Field(default="general", description="Knowledge domain scope")
    status: str = Field(default="uploaded", description="Upload status")
    document_metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    virus_scan_status: str = Field(default="pending", description="Virus scan result")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)

    @field_validator("extension")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Extension '{value}' is not allowed. Allowed: {ALLOWED_EXTENSIONS}")
        return normalized

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        if value not in ALLOWED_MIME_TYPES:
            raise ValueError(f"MIME type '{value}' is not allowed. Allowed: {ALLOWED_MIME_TYPES}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"pending", "uploading", "uploaded", "failed", "rejected"}
        if value not in allowed:
            raise ValueError(f"Status must be one of: {allowed}")
        return value

    @field_validator("virus_scan_status")
    @classmethod
    def validate_virus_scan(cls, value: str) -> str:
        allowed = {"pending", "clean", "infected", "skipped"}
        if value not in allowed:
            raise ValueError(f"Virus scan status must be one of: {allowed}")
        return value
