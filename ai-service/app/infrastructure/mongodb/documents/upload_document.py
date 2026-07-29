from typing import Any, Optional

from pydantic import Field

from app.domain.knowledge.entities.document_upload import DocumentUpload
from app.domain.knowledge.value_objects.document_metadata import DocumentMetadata
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument


class UploadMetadataModel(BaseMongoDocument):
    """MongoDB document model representing a DocumentUpload."""

    original_filename: str = Field(...)
    stored_filename: str = Field(...)
    file_path: str = Field(...)
    file_size: int = Field(..., ge=0)
    mime_type: str = Field(...)
    extension: str = Field(...)
    checksum: str = Field(..., index=True)
    content_type: str = Field(default="document")
    uploaded_by: str = Field(...)
    organization_id: str = Field(...)
    store_id: str = Field(..., index=True)
    knowledge_scope: str = Field(default="general")
    status: str = Field(default="uploaded", index=True)
    document_metadata: dict[str, Any] = Field(default_factory=dict)
    virus_scan_status: str = Field(default="pending")

    def to_entity(self) -> DocumentUpload:
        return DocumentUpload(
            id=str(self.id),
            original_filename=self.original_filename,
            stored_filename=self.stored_filename,
            file_path=self.file_path,
            file_size=self.file_size,
            mime_type=self.mime_type,
            extension=self.extension,
            checksum=self.checksum,
            content_type=self.content_type,
            uploaded_by=self.uploaded_by,
            organization_id=self.organization_id,
            store_id=self.store_id,
            knowledge_scope=self.knowledge_scope,
            status=self.status,
            document_metadata=DocumentMetadata(**self.document_metadata),
            virus_scan_status=self.virus_scan_status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            deleted_at=self.deleted_at,
        )

    @classmethod
    def from_entity(cls, entity: DocumentUpload) -> "UploadMetadataModel":
        return cls(
            _id=entity.id,
            original_filename=entity.original_filename,
            stored_filename=entity.stored_filename,
            file_path=entity.file_path,
            file_size=entity.file_size,
            mime_type=entity.mime_type,
            extension=entity.extension,
            checksum=entity.checksum,
            content_type=entity.content_type,
            uploaded_by=entity.uploaded_by,
            organization_id=entity.organization_id,
            store_id=entity.store_id,
            knowledge_scope=entity.knowledge_scope,
            status=entity.status,
            document_metadata=entity.document_metadata.model_dump(),
            virus_scan_status=entity.virus_scan_status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )
