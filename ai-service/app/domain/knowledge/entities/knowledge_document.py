from datetime import UTC, datetime
from typing import Optional

from pydantic import Field, model_validator

from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.domain.knowledge.exceptions import KnowledgeValidationException
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion
from app.shared.kernel.aggregate_root import AggregateRoot


class KnowledgeDocument(AggregateRoot[str]):
    """Domain aggregate root representing a knowledge base source document."""

    store_id: str = Field(..., description="Commerce store context ID")
    title: str = Field(..., description="Title of the document")
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of the document",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL source of the document if applicable",
    )
    status: str = Field(default="draft", description="Status of the document")
    language: str = Field(default="en", description="Document language")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    versions: list[DocumentVersion] = Field(default_factory=list)
    current_version: int = Field(default=1, ge=1)
    chunks: list[KnowledgeChunk] = Field(
        default_factory=list,
        description="Associated document chunks",
    )
    chunking_strategy: str = Field(
        default="manual",
        description="Chunking strategy label",
    )
    processed_text: Optional[str] = Field(
        default=None,
        description="Extracted and normalized text content after processing",
    )
    page_count: Optional[int] = Field(
        default=None,
        description="Number of pages in the source document",
    )
    word_count: Optional[int] = Field(
        default=None,
        description="Total word count of processed text",
    )
    char_count: Optional[int] = Field(
        default=None,
        description="Total character count of processed text",
    )
    estimated_tokens: Optional[int] = Field(
        default=None,
        description="Estimated token count using tiktoken",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    deleted_at: Optional[datetime] = Field(default=None)

    @model_validator(mode="after")
    def validate_versions(self) -> "KnowledgeDocument":
        if not self.versions:
            self.versions = [DocumentVersion(version_number=self.current_version, is_current=True)]
            return self

        version_numbers = {version.version_number for version in self.versions}
        if self.current_version not in version_numbers:
            raise KnowledgeValidationException(
                "Current version must exist in the document version history."
            )

        current_versions = [version for version in self.versions if version.is_current]
        if len(current_versions) > 1:
            raise KnowledgeValidationException(
                "Only one document version can be marked as current."
            )

        if not current_versions:
            for version in self.versions:
                version.is_current = version.version_number == self.current_version

        return self
