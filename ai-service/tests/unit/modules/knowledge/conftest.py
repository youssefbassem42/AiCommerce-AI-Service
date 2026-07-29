import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from app.application.knowledge.dto import (
    BusinessSummaryCreateDTO,
    BusinessSummaryDTO,
    BusinessSummaryUpdateDTO,
    DocumentMetadataDTO,
    DocumentVersionDTO,
    KnowledgeChunkCreateDTO,
    KnowledgeChunkDTO,
    KnowledgeChunkUpdateDTO,
    KnowledgeDocumentCreateDTO,
    KnowledgeDocumentDTO,
    KnowledgeDocumentUpdateDTO,
    PaginatedResultDTO,
)
from app.domain.knowledge.entities import BusinessSummary, KnowledgeChunk, KnowledgeDocument
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion


@pytest.fixture
def sample_metadata():
    return DocumentMetadata(
        source_type="manual",
        source_uri="https://example.com/doc",
        mime_type="application/pdf",
        language="en",
        category="guide",
        tags=["guide", "manual"],
    )


@pytest.fixture
def sample_metadata_dto():
    return DocumentMetadataDTO(
        source_type="manual",
        source_uri="https://example.com/doc",
        mime_type="application/pdf",
        language="en",
        category="guide",
        tags=["guide", "manual"],
    )


@pytest.fixture
def sample_version():
    return DocumentVersion(version_number=1, checksum="abc123", created_by="user-1", notes="Initial version", is_current=True)


@pytest.fixture
def sample_version_dto():
    return DocumentVersionDTO(version_number=1, checksum="abc123", created_by="user-1", notes="Initial version", is_current=True)


@pytest.fixture
def sample_document_entity(sample_metadata, sample_version):
    return KnowledgeDocument(
        id="doc-1",
        store_id="store-1",
        title="Test Document",
        description="A test document",
        source_url="https://example.com/doc",
        status="active",
        language="en",
        metadata=sample_metadata,
        versions=[sample_version],
        current_version=1,
        chunking_strategy="manual",
    )


@pytest.fixture
def sample_chunk_entity():
    return KnowledgeChunk(
        id="chunk-1",
        document_id="doc-1",
        version_number=1,
        chunk_index=0,
        title="Chunk 1",
        content="This is the first chunk content.",
        embedding_id=None,
        metadata={"section": "intro"},
    )


@pytest.fixture
def sample_summary_entity():
    return BusinessSummary(
        id="summary-1",
        document_id="doc-1",
        version_number=1,
        title="Executive Summary",
        summary="This is a business summary.",
        metadata={"author": "ai-system"},
    )


@pytest.fixture
def sample_document_create_dto(sample_metadata_dto, sample_version_dto):
    return KnowledgeDocumentCreateDTO(
        store_id="store-1",
        title="Test Document",
        description="A test document",
        source_url="https://example.com/doc",
        status="active",
        language="en",
        metadata=sample_metadata_dto,
        versions=[sample_version_dto],
        current_version=1,
        chunking_strategy="manual",
    )


@pytest.fixture
def sample_chunk_create_dto():
    return KnowledgeChunkCreateDTO(
        document_id="doc-1",
        version_number=1,
        chunk_index=0,
        title="Chunk 1",
        content="Content here",
        embedding_id=None,
        metadata={"section": "intro"},
    )


@pytest.fixture
def sample_summary_create_dto():
    return BusinessSummaryCreateDTO(
        document_id="doc-1",
        version_number=1,
        title="Executive Summary",
        summary="Business summary text.",
        metadata={"author": "ai-system"},
    )


@pytest.fixture
def sample_document_dto(sample_metadata_dto, sample_version_dto):
    return KnowledgeDocumentDTO(
        id="doc-1",
        store_id="store-1",
        title="Test Document",
        description="A test document",
        source_url="https://example.com/doc",
        status="active",
        language="en",
        metadata=sample_metadata_dto,
        versions=[sample_version_dto],
        current_version=1,
        chunks=[],
        chunking_strategy="manual",
        created_at="2025-01-01T00:00:00",
        updated_at="2025-01-01T00:00:00",
    )


@pytest.fixture
def mock_knowledge_repo():
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_many = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.paginate = AsyncMock()
    repo.bulk_insert = AsyncMock()
    repo.bulk_update = AsyncMock()
    repo.exists = AsyncMock()
    repo.find_by_store_id = AsyncMock()
    repo.find_by_status = AsyncMock()
    return repo


@pytest.fixture
def mock_chunk_repo():
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_many = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.paginate = AsyncMock()
    repo.bulk_insert = AsyncMock()
    repo.bulk_update = AsyncMock()
    repo.exists = AsyncMock()
    repo.find_by_document_id = AsyncMock()
    return repo


@pytest.fixture
def mock_summary_repo():
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_many = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.paginate = AsyncMock()
    repo.bulk_insert = AsyncMock()
    repo.bulk_update = AsyncMock()
    repo.exists = AsyncMock()
    repo.find_by_document_id = AsyncMock()
    return repo
