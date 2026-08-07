from pydantic import BaseModel, Field


class ProcessDocumentRequestSchema(BaseModel):
    document_id: str = Field(..., description="ID of the uploaded document to process")
    file_path: str | None = Field(
        default=None,
        description="Path to the document file (defaults to the document's stored source_url)",
    )
    mime_type: str | None = Field(default=None)
    also_chunk: bool = Field(default=True, description="Automatically chunk after processing")
    strategy: str = Field(default="recursive_character")
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    overlap: int = Field(default=200, ge=0, le=1000)
    store_id: str | None = None
    organization_id: str | None = None
    triggered_by: str | None = None


class ChunkDocumentRequestSchema(BaseModel):
    document_id: str
    strategy: str = Field(default="recursive_character")
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    overlap: int = Field(default=200, ge=0, le=1000)
    store_id: str | None = None
    organization_id: str | None = None
    triggered_by: str | None = None


class EmbedDocumentRequestSchema(BaseModel):
    document_id: str = Field(..., description="Embed all chunks of this document")
    model: str = Field(default="gemini-embedding-001")
    sync_to_vector_store: bool = Field(default=True, description="Sync vectors to Qdrant after embedding")
    collection_name: str = Field(default="kb_default")
    store_id: str | None = None
    organization_id: str | None = None
    triggered_by: str | None = None


class AsyncJobAcceptedResponseSchema(BaseModel):
    job_id: str
    job_type: str
    status: str = "pending"
    message: str
