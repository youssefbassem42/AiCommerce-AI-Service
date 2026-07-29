import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mongo_patch():
    """Prevent MongoDB connection when importing app.main."""
    with patch("app.infrastructure.mongodb.client.MongoClientManager.get_database") as mock_get_db:
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db
        yield


@pytest.fixture
def mock_doc_service():
    svc = MagicMock()
    svc.create = AsyncMock()
    svc.get_by_id = AsyncMock()
    svc.list = AsyncMock()
    svc.update = AsyncMock()
    svc.delete = AsyncMock()
    return svc


@pytest.fixture
def mock_chunk_service():
    svc = MagicMock()
    svc.create = AsyncMock()
    svc.get_by_id = AsyncMock()
    svc.list = AsyncMock()
    svc.update = AsyncMock()
    svc.delete = AsyncMock()
    return svc


@pytest.fixture
def mock_summary_service():
    svc = MagicMock()
    svc.create = AsyncMock()
    svc.get_by_id = AsyncMock()
    svc.list = AsyncMock()
    svc.update = AsyncMock()
    svc.delete = AsyncMock()
    return svc


@pytest.fixture(autouse=True)
def override_deps_and_app(mock_doc_service, mock_chunk_service, mock_summary_service):
    from app.main import app
    from app.api.knowledge.dependencies import (
        get_knowledge_document_service,
        get_knowledge_chunk_service,
        get_business_summary_service,
    )
    from app.api.knowledge.router import router as knowledge_router

    app.dependency_overrides.clear()
    overrides = {
        get_knowledge_document_service: lambda: mock_doc_service,
        get_knowledge_chunk_service: lambda: mock_chunk_service,
        get_business_summary_service: lambda: mock_summary_service,
    }
    app.dependency_overrides.update(overrides)
    if not any(r.path == "/api/v1/knowledge-base" for r in app.routes if hasattr(r, "path")):
        app.include_router(knowledge_router)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


class TestKnowledgeDocumentEndpoints:
    def _make_doc_dto(self, **overrides):
        from datetime import datetime
        from app.application.knowledge.dto import DocumentMetadataDTO, DocumentVersionDTO, KnowledgeDocumentDTO

        defaults = dict(
            id="doc-1", store_id="store-1", title="Test Doc", status="draft", language="en",
            metadata=DocumentMetadataDTO(), versions=[], current_version=1, chunks=[],
            chunking_strategy="manual", created_at=datetime.now(), updated_at=datetime.now(),
        )
        defaults.update(overrides)
        return KnowledgeDocumentDTO(**defaults)

    def test_create_document(self, client, mock_doc_service):
        mock_doc_service.create.return_value = self._make_doc_dto()

        payload = {"store_id": "store-1", "title": "Test Doc", "status": "draft"}
        resp = client.post("/api/v1/knowledge-base/documents", json=payload)
        assert resp.status_code == 201

    def test_get_document(self, client, mock_doc_service):
        mock_doc_service.get_by_id.return_value = self._make_doc_dto()

        resp = client.get("/api/v1/knowledge-base/documents/doc-1")
        assert resp.status_code == 200

    def test_get_document_not_found(self, client, mock_doc_service):
        from app.domain.knowledge.exceptions import KnowledgeDocumentNotFoundException

        mock_doc_service.get_by_id.side_effect = KnowledgeDocumentNotFoundException("Not found")

        resp = client.get("/api/v1/knowledge-base/documents/nonexistent")
        assert resp.status_code == 404

    def test_list_documents(self, client, mock_doc_service):
        from app.application.knowledge.dto import PaginatedResultDTO

        mock_doc_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)

        resp = client.get("/api/v1/knowledge-base/documents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_update_document(self, client, mock_doc_service):
        mock_doc_service.update.return_value = self._make_doc_dto(title="Updated", status="active")

        resp = client.put("/api/v1/knowledge-base/documents/doc-1", json={"title": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_delete_document(self, client, mock_doc_service):
        mock_doc_service.delete.return_value = True

        resp = client.delete("/api/v1/knowledge-base/documents/doc-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_document_not_found(self, client, mock_doc_service):
        from app.domain.knowledge.exceptions import KnowledgeDocumentNotFoundException

        mock_doc_service.delete.side_effect = KnowledgeDocumentNotFoundException("Not found")

        resp = client.delete("/api/v1/knowledge-base/documents/nonexistent")
        assert resp.status_code == 404


class TestKnowledgeChunkEndpoints:
    def _make_chunk_dto(self, **overrides):
        from datetime import datetime
        from app.application.knowledge.dto import KnowledgeChunkDTO

        defaults = dict(
            id="chunk-1", document_id="doc-1", version_number=1, chunk_index=0,
            content="Hello", metadata={}, created_at=datetime.now(), updated_at=datetime.now(),
        )
        defaults.update(overrides)
        return KnowledgeChunkDTO(**defaults)

    def test_create_chunk(self, client, mock_chunk_service):
        mock_chunk_service.create.return_value = self._make_chunk_dto()

        payload = {"document_id": "doc-1", "chunk_index": 0, "content": "Hello"}
        resp = client.post("/api/v1/knowledge-base/chunks", json=payload)
        assert resp.status_code == 201

    def test_get_chunk(self, client, mock_chunk_service):
        mock_chunk_service.get_by_id.return_value = self._make_chunk_dto()

        resp = client.get("/api/v1/knowledge-base/chunks/chunk-1")
        assert resp.status_code == 200

    def test_get_chunk_not_found(self, client, mock_chunk_service):
        from app.domain.knowledge.exceptions import KnowledgeChunkNotFoundException

        mock_chunk_service.get_by_id.side_effect = KnowledgeChunkNotFoundException("Not found")

        resp = client.get("/api/v1/knowledge-base/chunks/nonexistent")
        assert resp.status_code == 404

    def test_list_chunks(self, client, mock_chunk_service):
        from app.application.knowledge.dto import PaginatedResultDTO

        mock_chunk_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)

        resp = client.get("/api/v1/knowledge-base/chunks")
        assert resp.status_code == 200

    def test_update_chunk(self, client, mock_chunk_service):
        mock_chunk_service.update.return_value = self._make_chunk_dto(content="Updated")

        resp = client.put("/api/v1/knowledge-base/chunks/chunk-1", json={"content": "Updated"})
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated"

    def test_delete_chunk(self, client, mock_chunk_service):
        mock_chunk_service.delete.return_value = True

        resp = client.delete("/api/v1/knowledge-base/chunks/chunk-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_chunk_not_found(self, client, mock_chunk_service):
        from app.domain.knowledge.exceptions import KnowledgeChunkNotFoundException

        mock_chunk_service.delete.side_effect = KnowledgeChunkNotFoundException("Not found")

        resp = client.delete("/api/v1/knowledge-base/chunks/nonexistent")
        assert resp.status_code == 404


class TestBusinessSummaryEndpoints:
    def _make_summary_dto(self, **overrides):
        from datetime import datetime
        from app.application.knowledge.dto import BusinessSummaryDTO

        defaults = dict(
            id="sum-1", document_id="doc-1", version_number=1,
            title="Summary", summary="Body", metadata={},
            created_at=datetime.now(), updated_at=datetime.now(),
        )
        defaults.update(overrides)
        return BusinessSummaryDTO(**defaults)

    def test_create_summary(self, client, mock_summary_service):
        mock_summary_service.create.return_value = self._make_summary_dto()

        payload = {"document_id": "doc-1", "title": "Summary", "summary": "Body"}
        resp = client.post("/api/v1/knowledge-base/summaries", json=payload)
        assert resp.status_code == 201

    def test_get_summary(self, client, mock_summary_service):
        mock_summary_service.get_by_id.return_value = self._make_summary_dto()

        resp = client.get("/api/v1/knowledge-base/summaries/sum-1")
        assert resp.status_code == 200

    def test_get_summary_not_found(self, client, mock_summary_service):
        from app.domain.knowledge.exceptions import BusinessSummaryNotFoundException

        mock_summary_service.get_by_id.side_effect = BusinessSummaryNotFoundException("Not found")

        resp = client.get("/api/v1/knowledge-base/summaries/nonexistent")
        assert resp.status_code == 404

    def test_list_summaries(self, client, mock_summary_service):
        from app.application.knowledge.dto import PaginatedResultDTO

        mock_summary_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)

        resp = client.get("/api/v1/knowledge-base/summaries")
        assert resp.status_code == 200

    def test_update_summary(self, client, mock_summary_service):
        mock_summary_service.update.return_value = self._make_summary_dto(summary="Updated body")

        resp = client.put("/api/v1/knowledge-base/summaries/sum-1", json={"summary": "Updated body"})
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Updated body"

    def test_delete_summary(self, client, mock_summary_service):
        mock_summary_service.delete.return_value = True

        resp = client.delete("/api/v1/knowledge-base/summaries/sum-1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_summary_not_found(self, client, mock_summary_service):
        from app.domain.knowledge.exceptions import BusinessSummaryNotFoundException

        mock_summary_service.delete.side_effect = BusinessSummaryNotFoundException("Not found")

        resp = client.delete("/api/v1/knowledge-base/summaries/nonexistent")
        assert resp.status_code == 404
