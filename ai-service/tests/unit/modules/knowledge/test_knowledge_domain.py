import pytest
from datetime import UTC, datetime

from app.domain.knowledge.entities import BusinessSummary, KnowledgeChunk, KnowledgeDocument
from app.domain.knowledge.value_objects import DocumentMetadata, DocumentVersion
from app.domain.knowledge.exceptions import KnowledgeValidationException


class TestDocumentMetadata:
    def test_create_default(self):
        meta = DocumentMetadata()
        assert meta.source_type == "manual"
        assert meta.language == "en"
        assert meta.tags == []

    def test_normalize_tags(self):
        meta = DocumentMetadata(tags=[" tag1 ", " tag2 ", ""])
        assert meta.tags == ["tag1", "tag2"]

    def test_full_metadata(self):
        meta = DocumentMetadata(
            source_type="upload",
            source_uri="https://example.com/file.pdf",
            mime_type="application/pdf",
            language="fr",
            category="legal",
            tags=["contract", "2025"],
            attributes={"pages": 10},
        )
        assert meta.source_type == "upload"
        assert meta.mime_type == "application/pdf"
        assert meta.attributes == {"pages": 10}


class TestDocumentVersion:
    def test_create_default(self):
        ver = DocumentVersion(version_number=1)
        assert ver.version_number == 1
        assert ver.is_current is False
        assert ver.created_at is not None

    def test_create_full(self):
        dt = datetime.now(UTC)
        ver = DocumentVersion(
            version_number=2,
            checksum="sha256:abc",
            created_by="user-1",
            notes="Updated content",
            is_current=True,
            created_at=dt,
        )
        assert ver.checksum == "sha256:abc"
        assert ver.is_current is True


class TestKnowledgeDocument:
    def test_create_minimal(self):
        doc = KnowledgeDocument(
            id="doc-1",
            store_id="store-1",
            title="Test Doc",
        )
        assert doc.id == "doc-1"
        assert doc.status == "draft"
        assert doc.language == "en"
        assert doc.current_version == 1
        assert doc.chunking_strategy == "manual"
        assert len(doc.versions) == 1
        assert doc.versions[0].version_number == 1

    def test_create_with_metadata(self, sample_metadata, sample_version):
        doc = KnowledgeDocument(
            id="doc-2",
            store_id="store-1",
            title="Rich Doc",
            description="A rich document",
            source_url="https://example.com/doc",
            status="active",
            language="de",
            metadata=sample_metadata,
            versions=[sample_version],
            current_version=1,
            chunking_strategy="token",
        )
        assert doc.metadata.source_type == "manual"
        assert doc.versions[0].checksum == "abc123"
        assert doc.status == "active"

    def test_validate_versions_no_current_version(self, sample_metadata):
        v1 = DocumentVersion(version_number=1)
        v2 = DocumentVersion(version_number=2)
        doc = KnowledgeDocument(
            id="doc-3",
            store_id="store-1",
            title="Doc",
            versions=[v1, v2],
            current_version=2,
        )
        current = [v for v in doc.versions if v.is_current]
        assert len(current) == 1
        assert current[0].version_number == 2

    def test_validate_versions_current_version_missing(self):
        v1 = DocumentVersion(version_number=1, is_current=True)
        with pytest.raises(KnowledgeValidationException):
            KnowledgeDocument(
                id="doc-4",
                store_id="store-1",
                title="Bad Doc",
                versions=[v1],
                current_version=3,
            )

    def test_validate_versions_multiple_current(self):
        v1 = DocumentVersion(version_number=1, is_current=True)
        v2 = DocumentVersion(version_number=2, is_current=True)
        with pytest.raises(KnowledgeValidationException):
            KnowledgeDocument(
                id="doc-5",
                store_id="store-1",
                title="Bad Doc",
                versions=[v1, v2],
                current_version=1,
            )


class TestKnowledgeChunk:
    def test_create_minimal(self):
        chunk = KnowledgeChunk(
            id="chunk-1",
            document_id="doc-1",
            chunk_index=0,
            content="Hello world",
        )
        assert chunk.version_number == 1
        assert chunk.embedding_id is None
        assert chunk.metadata == {}
        assert chunk.created_at is not None

    def test_create_full(self):
        chunk = KnowledgeChunk(
            id="chunk-2",
            document_id="doc-1",
            version_number=2,
            chunk_index=1,
            title="Second Chunk",
            content="More content",
            embedding_id="emb-001",
            metadata={"page": 5},
        )
        assert chunk.embedding_id == "emb-001"
        assert chunk.metadata["page"] == 5


class TestBusinessSummary:
    def test_create_minimal(self):
        summary = BusinessSummary(
            id="sum-1",
            document_id="doc-1",
            title="Summary",
            summary="Text body",
        )
        assert summary.version_number == 1
        assert summary.metadata == {}

    def test_create_full(self):
        summary = BusinessSummary(
            id="sum-2",
            document_id="doc-1",
            version_number=3,
            title="V3 Summary",
            summary="Updated summary content",
            metadata={"version_label": "final"},
        )
        assert summary.metadata["version_label"] == "final"
