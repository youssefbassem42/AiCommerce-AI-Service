from dataclasses import dataclass
from typing import Any


@dataclass
class UploadDocumentCommand:
    """Command to upload a file to the knowledge base."""

    file_path: str
    original_filename: str
    mime_type: str
    file_size: int
    uploaded_by: str
    organization_id: str | None = None
    store_id: str | None = None
    knowledge_scope: str = "general"
    document_metadata: dict[str, Any] | None = None
