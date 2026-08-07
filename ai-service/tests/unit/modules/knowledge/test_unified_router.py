from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mongo_patch():
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


@pytest.fixture
def mock_retriever():
    r = AsyncMock()
    r.search = AsyncMock()
    return r


@pytest.fixture
def mock_job_repo():
    r = MagicMock()
    r.find_by_id = AsyncMock()
    return r


@pytest.fixture
def mock_upload_service():
    svc = MagicMock()
    svc.upload = AsyncMock()
    return svc


@pytest.fixture(autouse=True)
def override_deps(
    mock_doc_service,
    mock_chunk_service,
    mock_summary_service,
    mock_retriever,
    mock_job_repo,
    mock_upload_service,
):
    from app.api.knowledge.dependencies import (
        get_business_summary_service,
        get_document_upload_service,
        get_knowledge_chunk_service,
        get_knowledge_document_service,
    )
    from app.api.knowledge.retrieval_dependencies import get_retriever_service
    from app.main import app
    from tests.conftest import override_auth_dependencies

    overrides = {
        get_knowledge_document_service: lambda: mock_doc_service,
        get_knowledge_chunk_service: lambda: mock_chunk_service,
        get_business_summary_service: lambda: mock_summary_service,
        get_document_upload_service: lambda: mock_upload_service,
        get_retriever_service: lambda: mock_retriever,
    }
    app.dependency_overrides.clear()
    app.dependency_overrides.update(overrides)
    override_auth_dependencies(app)

    if not any(getattr(r, "path", None) and "/api/v1/knowledge-base" in str(r.path) for r in app.routes):
        from app.api.knowledge.unified_router import router as unified_router

        app.include_router(unified_router)

    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def make_doc_dto(**overrides):
    from app.application.knowledge.dto import DocumentMetadataDTO, KnowledgeDocumentDTO

    defaults = {
        "id": "doc-1",
        "store_id": "store-1",
        "title": "Test Doc",
        "status": "processing",
        "language": "en",
        "metadata": DocumentMetadataDTO(),
        "versions": [],
        "current_version": 1,
        "chunks": [],
        "chunking_strategy": "manual",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    defaults.update(overrides)
    return KnowledgeDocumentDTO(**defaults)


class TestUnifiedDocumentEndpoints:
    def test_list_documents(self, client, mock_doc_service):
        from app.application.knowledge.dto import PaginatedResultDTO

        mock_doc_service.list.return_value = PaginatedResultDTO(items=[], total=0, page=1, page_size=20)

        resp = client.get("/api/v1/knowledge-base/documents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_document(self, client, mock_doc_service):
        mock_doc_service.get_by_id.return_value = make_doc_dto()

        resp = client.get("/api/v1/knowledge-base/documents/doc-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "doc-1"

    def test_get_document_not_found(self, client, mock_doc_service):
        from app.domain.knowledge.exceptions import KnowledgeDocumentNotFoundException

        mock_doc_service.get_by_id.side_effect = KnowledgeDocumentNotFoundException("Not found")

        resp = client.get("/api/v1/knowledge-base/documents/nonexistent")
        assert resp.status_code == 404

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


class TestUploadScoping:
    """Upload must work when the JWT has no org/store claims (.NET never issues org).

    Contract: org/store are optional claims; missing claims fall back to the
    "default" tenant partition instead of 403.
    """

    @pytest.fixture
    def missing_tenant_claims(self, client):
        from app.api.auth import dependencies as auth_deps
        from app.main import app

        app.dependency_overrides[auth_deps.get_optional_organization_id] = lambda: None
        app.dependency_overrides[auth_deps.get_optional_store_id] = lambda: None
        yield
        app.dependency_overrides.clear()

    def _upload(self, client):
        return client.post(
            "/api/v1/knowledge-base/upload",
            files={"file": ("sample.txt", b"hello", "text/plain")},
        )

    def test_upload_ok_without_org_or_store_claims(self, client, mock_upload_service, missing_tenant_claims):
        from app.application.knowledge.dto import UploadDTO

        mock_upload_service.upload.return_value = UploadDTO(
            id="up-1",
            original_filename="sample.txt",
            stored_filename="up-1.txt",
            file_path="/tmp/up-1.txt",
            file_size=5,
            mime_type="text/plain",
            extension=".txt",
            checksum="abc",
            content_type="text/plain",
            uploaded_by="11111111-1111-1111-1111-111111111111",
            organization_id="default",
            store_id="default",
            knowledge_scope="general",
            status="uploaded",
            document_metadata=__import__(
                "app.application.knowledge.dto", fromlist=["DocumentMetadataDTO"]
            ).DocumentMetadataDTO(),
            virus_scan_status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        resp = self._upload(client)
        assert resp.status_code == 201

        command = mock_upload_service.upload.await_args.args[0]
        assert command.organization_id == "default"
        assert command.store_id == "default"
        assert command.uploaded_by == "11111111-1111-1111-1111-111111111111"

    def test_upload_keeps_claims_when_present(self, client, mock_upload_service):
        from app.application.knowledge.dto import UploadDTO

        mock_upload_service.upload.return_value = UploadDTO(
            id="up-2",
            original_filename="sample.txt",
            stored_filename="up-2.txt",
            file_path="/tmp/up-2.txt",
            file_size=5,
            mime_type="text/plain",
            extension=".txt",
            checksum="def",
            content_type="text/plain",
            uploaded_by="11111111-1111-1111-1111-111111111111",
            organization_id="org-1",
            store_id="store-1",
            knowledge_scope="general",
            status="uploaded",
            document_metadata=__import__(
                "app.application.knowledge.dto", fromlist=["DocumentMetadataDTO"]
            ).DocumentMetadataDTO(),
            virus_scan_status="pending",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        resp = client.post(
            "/api/v1/knowledge-base/upload",
            files={"file": ("sample.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 201

        command = mock_upload_service.upload.await_args.args[0]
        assert command.organization_id == "org-1"
        assert command.store_id == "store-1"


class TestUnifiedAsyncEndpoints:
    @patch("app.application.jobs.job_dispatcher.set_celery_task_id", new_callable=AsyncMock)
    @patch("app.application.jobs.job_dispatcher.create_job", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.process_document_task")
    def test_process_document(self, mock_task, mock_create_job, mock_set_task, client):
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/api/v1/knowledge-base/process",
            json={
                "document_id": "doc-1",
                "file_path": "/tmp/test.pdf",
                "also_chunk": False,
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == "job-1"
        assert data["job_type"] == "document_processing"

    @patch("app.application.jobs.job_dispatcher.set_celery_task_id", new_callable=AsyncMock)
    @patch("app.application.jobs.job_dispatcher.create_job", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.generate_chunks_task")
    def test_chunk_document(self, mock_task, mock_create_job, mock_set_task, client):
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/api/v1/knowledge-base/chunk",
            json={
                "document_id": "doc-1",
                "strategy": "recursive_character",
                "chunk_size": 1000,
                "overlap": 200,
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["job_id"] == "job-1"

    @patch("app.application.jobs.job_dispatcher.set_celery_task_id", new_callable=AsyncMock)
    @patch("app.application.jobs.job_dispatcher.create_job", new_callable=AsyncMock)
    @patch("app.workers.embedding.tasks.generate_embeddings_task")
    def test_embed_document(self, mock_task, mock_create_job, mock_set_task, client):
        with patch("app.infrastructure.mongodb.repositories.chunk_repository.ChunkRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.find_by_document_id = AsyncMock(return_value=[MagicMock(id="chunk-1")])
            mock_repo_cls.return_value = mock_repo

            mock_job = MagicMock()
            mock_job.id = "job-1"
            mock_create_job.return_value = mock_job
            mock_task.delay.return_value = MagicMock(id="celery-1")

            resp = client.post(
                "/api/v1/knowledge-base/embed",
                json={
                    "document_id": "doc-1",
                    "sync_to_vector_store": False,
                },
            )
            assert resp.status_code == 202

    def test_embed_document_no_chunks(self, client):
        with patch("app.infrastructure.mongodb.repositories.chunk_repository.ChunkRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.find_by_document_id = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            resp = client.post(
                "/api/v1/knowledge-base/embed",
                json={
                    "document_id": "doc-1",
                    "sync_to_vector_store": False,
                },
            )
            assert resp.status_code == 404


class TestUnifiedSearchEndpoints:
    def test_search_semantic(self, client, mock_retriever):
        from app.application.knowledge.retrieval.dto import UnifiedRetrievalResult

        mock_retriever.search.return_value = UnifiedRetrievalResult(
            query="test",
            results=[],
            total_count=0,
            strategy="semantic",
            latency_ms=10.0,
            filters_applied={},
        )

        resp = client.post("/api/v1/knowledge-base/search", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "semantic"
        assert data["total_count"] == 0

    def test_search_hybrid(self, client, mock_retriever):
        from app.application.knowledge.retrieval.dto import UnifiedRetrievalResult

        mock_retriever.search.return_value = UnifiedRetrievalResult(
            query="test",
            results=[],
            total_count=0,
            strategy="hybrid",
            latency_ms=10.0,
            filters_applied={},
        )

        resp = client.post("/api/v1/knowledge-base/search/hybrid", json={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "hybrid"


class TestUnifiedJobEndpoint:
    def _override_job_repo(self, client, mock_job_repo):
        from app.api.knowledge.unified_router import _get_job_repository

        client.app.dependency_overrides[_get_job_repository] = lambda: mock_job_repo

    def _restore_job_repo(self, client):
        from app.api.knowledge.unified_router import _get_job_repository

        client.app.dependency_overrides.pop(_get_job_repository, None)

    def test_get_job_found(self, client, mock_job_repo):
        from app.domain.job.entities.knowledge_job import KnowledgeJob
        from app.domain.job.value_objects import JobStatus, JobType

        job = KnowledgeJob(id="job-1", job_type=JobType.DOCUMENT_PROCESSING, status=JobStatus.COMPLETED)
        mock_job_repo.find_by_id.return_value = job

        self._override_job_repo(client, mock_job_repo)
        try:
            resp = client.get("/api/v1/knowledge-base/jobs/job-1")
            assert resp.status_code == 200
            assert resp.json()["id"] == "job-1"
        finally:
            self._restore_job_repo(client)

    def test_get_job_not_found(self, client, mock_job_repo):
        mock_job_repo.find_by_id.return_value = None

        self._override_job_repo(client, mock_job_repo)
        try:
            resp = client.get("/api/v1/knowledge-base/jobs/nonexistent")
            assert resp.status_code == 404
        finally:
            self._restore_job_repo(client)
