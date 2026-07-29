import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType


@pytest.fixture(autouse=True)
def mongo_patch():
    with patch("app.infrastructure.mongodb.client.MongoClientManager.get_database") as mock:
        yield


@pytest.fixture
def mock_job_repo():
    repo = MagicMock()
    repo.find_by_id = AsyncMock()
    repo.paginate = AsyncMock()
    repo.find_many = AsyncMock()
    repo.find_by_status = AsyncMock()
    repo.find_by_type_and_status = AsyncMock()
    repo.find_dead_letters = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.exists = AsyncMock()
    repo.update_progress = AsyncMock()
    repo.mark_completed = AsyncMock()
    repo.mark_failed = AsyncMock()
    repo.bulk_insert = AsyncMock()
    repo.bulk_update = AsyncMock()
    return repo


@pytest.fixture(autouse=True)
def override_deps(mock_job_repo):
    from app.main import app
    from app.api.knowledge.job_router import get_job_repository

    app.dependency_overrides.clear()
    app.dependency_overrides[get_job_repository] = lambda: mock_job_repo

    if not any(getattr(r, 'path', None) and "/knowledge/jobs" in str(r.path) for r in app.routes):
        from app.api.knowledge.job_router import router as job_router
        app.include_router(job_router)

    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def make_knowledge_job(job_id: str = "507f1f77bcf86cd799439011", **overrides) -> KnowledgeJob:
    defaults = dict(
        id=job_id,
        job_type=JobType.DOCUMENT_PROCESSING,
        status=JobStatus.PENDING,
        progress=0.0,
        payload={},
        result=None,
        error_message=None,
        retry_count=0,
        max_retries=3,
        store_id="store-1",
        organization_id="org-1",
        triggered_by=None,
        celery_task_id=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    defaults.update(overrides)
    return KnowledgeJob(**defaults)


class TestJobRouterGetJob:
    def test_get_job_found(self, client, mock_job_repo):
        job = make_knowledge_job(status=JobStatus.COMPLETED, result={"ok": True})
        mock_job_repo.find_by_id.return_value = job

        resp = client.get("/knowledge/jobs/507f1f77bcf86cd799439011")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "507f1f77bcf86cd799439011"
        assert data["status"] == "completed"
        assert data["result"] == {"ok": True}
        assert data["store_id"] == "store-1"

    def test_get_job_not_found(self, client, mock_job_repo):
        mock_job_repo.find_by_id.return_value = None

        resp = client.get("/knowledge/jobs/nonexistent")
        assert resp.status_code == 404


class TestJobRouterListJobs:
    def test_list_jobs_empty(self, client, mock_job_repo):
        mock_job_repo.paginate = AsyncMock(return_value=([], 0))

        resp = client.get("/knowledge/jobs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_jobs_with_filters(self, client, mock_job_repo):
        mock_job_repo.paginate = AsyncMock(return_value=([make_knowledge_job()], 1))

        resp = client.get("/knowledge/jobs?status=failed&job_type=document_processing&store_id=store-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


class TestJobRouterRequeue:
    def test_requeue_job_found(self, client, mock_job_repo):
        original = make_knowledge_job(status=JobStatus.DEAD_LETTER, error_message="Failed")
        requeued = make_knowledge_job(status=JobStatus.PENDING, error_message=None, retry_count=0)

        mock_job_repo.find_by_id = AsyncMock()
        mock_job_repo.find_by_id.side_effect = [original, requeued]

        with patch("app.api.knowledge.job_router.requeue_dead_letter", AsyncMock()):
            resp = client.post("/knowledge/jobs/507f1f77bcf86cd799439011/requeue")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "pending"

    def test_requeue_job_not_found(self, client, mock_job_repo):
        mock_job_repo.find_by_id.return_value = None

        resp = client.post("/knowledge/jobs/nonexistent/requeue")
        assert resp.status_code == 404


class TestJobRouterCreateJobs:
    @patch("app.api.knowledge.job_router._run_async")
    @patch("app.workers.ingestion.tasks.process_document_task")
    @patch("app.api.knowledge.job_router.create_job", new_callable=AsyncMock)
    def test_create_document_processing_job(self, mock_create_job, mock_task, mock_run_async, client):
        mock_job = make_knowledge_job(job_type=JobType.DOCUMENT_PROCESSING)
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/knowledge/jobs/document-processing",
            params={
                "document_id": "doc-1",
                "file_path": "/tmp/test.pdf",
                "store_id": "store-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["job_type"] == "document_processing"
        assert data["status"] == "pending"

    @patch("app.api.knowledge.job_router._run_async")
    @patch("app.workers.ingestion.tasks.generate_chunks_task")
    @patch("app.api.knowledge.job_router.create_job", new_callable=AsyncMock)
    def test_create_chunk_generation_job(self, mock_create_job, mock_task, mock_run_async, client):
        mock_job = make_knowledge_job(job_type=JobType.CHUNK_GENERATION)
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/knowledge/jobs/chunk-generation",
            params={"document_id": "doc-1"},
        )
        assert resp.status_code == 201

    @patch("app.api.knowledge.job_router._run_async")
    @patch("app.workers.summarization.tasks.generate_summary_task")
    @patch("app.api.knowledge.job_router.create_job", new_callable=AsyncMock)
    def test_create_summary_generation_job(self, mock_create_job, mock_task, mock_run_async, client):
        mock_job = make_knowledge_job(job_type=JobType.SUMMARY_GENERATION)
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/knowledge/jobs/summary-generation",
            params={"store_id": "store-1"},
        )
        assert resp.status_code == 201

    @patch("app.api.knowledge.job_router._run_async")
    @patch("app.workers.embedding.tasks.generate_embeddings_task")
    @patch("app.api.knowledge.job_router.create_job", new_callable=AsyncMock)
    def test_create_embedding_generation_job(self, mock_create_job, mock_task, mock_run_async, client):
        mock_job = make_knowledge_job(job_type=JobType.EMBEDDING_GENERATION)
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/knowledge/jobs/embedding-generation",
            params={"chunk_ids": ["c1", "c2"]},
        )
        assert resp.status_code == 201

    @patch("app.api.knowledge.job_router._run_async")
    @patch("app.workers.embedding.tasks.sync_vectors_task")
    @patch("app.api.knowledge.job_router.create_job", new_callable=AsyncMock)
    def test_create_vector_sync_job(self, mock_create_job, mock_task, mock_run_async, client):
        mock_job = make_knowledge_job(job_type=JobType.VECTOR_SYNC)
        mock_create_job.return_value = mock_job
        mock_task.delay.return_value = MagicMock(id="celery-1")

        resp = client.post(
            "/knowledge/jobs/vector-sync",
            params={"chunk_ids": ["c1"]},
        )
        assert resp.status_code == 201
