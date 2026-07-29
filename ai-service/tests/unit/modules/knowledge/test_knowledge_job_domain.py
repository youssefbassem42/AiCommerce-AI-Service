import pytest
from datetime import UTC, datetime

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType
from app.domain.job.exceptions import JobNotFoundException, JobAlreadyCompletedException, JobMaxRetriesExceededException


class TestJobType:
    def test_values(self):
        assert JobType.DOCUMENT_PROCESSING == "document_processing"
        assert JobType.CHUNK_GENERATION == "chunk_generation"
        assert JobType.SUMMARY_GENERATION == "summary_generation"
        assert JobType.EMBEDDING_GENERATION == "embedding_generation"
        assert JobType.VECTOR_SYNC == "vector_sync"

    def test_members(self):
        assert len(JobType) == 5


class TestJobStatus:
    def test_values(self):
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.RETRYING == "retrying"
        assert JobStatus.DEAD_LETTER == "dead_letter"

    def test_members(self):
        assert len(JobStatus) == 6


class TestKnowledgeJob:
    def test_create_minimal(self):
        job = KnowledgeJob(
            id="job-1",
            job_type=JobType.DOCUMENT_PROCESSING,
        )
        assert job.id == "job-1"
        assert job.job_type == JobType.DOCUMENT_PROCESSING
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0
        assert job.payload == {}
        assert job.result is None
        assert job.error_message is None
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.store_id is None
        assert job.organization_id is None
        assert job.triggered_by is None
        assert job.celery_task_id is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.created_at is not None
        assert job.updated_at is not None

    def test_create_full(self):
        dt = datetime.now(UTC)
        job = KnowledgeJob(
            id="job-2",
            job_type=JobType.EMBEDDING_GENERATION,
            status=JobStatus.RUNNING,
            progress=0.5,
            payload={"document_id": "doc-1"},
            result={"chunks": 10},
            error_message=None,
            retry_count=1,
            max_retries=5,
            store_id="store-1",
            organization_id="org-1",
            triggered_by="user-1",
            celery_task_id="celery-task-1",
            started_at=dt,
            completed_at=None,
            created_at=dt,
            updated_at=dt,
        )
        assert job.job_type == JobType.EMBEDDING_GENERATION
        assert job.status == JobStatus.RUNNING
        assert job.progress == 0.5
        assert job.payload["document_id"] == "doc-1"
        assert job.result["chunks"] == 10
        assert job.retry_count == 1
        assert job.max_retries == 5
        assert job.celery_task_id == "celery-task-1"

    def test_status_enum_values(self):
        job = KnowledgeJob(id="job-3", job_type=JobType.CHUNK_GENERATION, status=JobStatus.FAILED)
        assert job.status.value == "failed"

    def test_progress_valid_range(self):
        job = KnowledgeJob(id="job-4", job_type=JobType.SUMMARY_GENERATION, progress=0.0)
        assert job.progress == 0.0
        job.progress = 1.0
        assert job.progress == 1.0

    def test_retry_count_default(self):
        job = KnowledgeJob(id="job-5", job_type=JobType.VECTOR_SYNC)
        assert job.retry_count == 0

    def test_max_retries_default(self):
        job = KnowledgeJob(id="job-6", job_type=JobType.DOCUMENT_PROCESSING)
        assert job.max_retries == 3


class TestJobExceptions:
    def test_job_not_found(self):
        exc = JobNotFoundException("Job not found")
        assert str(exc) == "Job not found"
        assert isinstance(exc, Exception)

    def test_job_already_completed(self):
        exc = JobAlreadyCompletedException("Already done")
        assert str(exc) == "Already done"

    def test_job_max_retries_exceeded(self):
        exc = JobMaxRetriesExceededException("Max retries exceeded")
        assert str(exc) == "Max retries exceeded"
