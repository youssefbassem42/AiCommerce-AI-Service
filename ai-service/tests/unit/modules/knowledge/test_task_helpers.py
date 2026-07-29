import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import UTC, datetime

from app.domain.job.value_objects import JobStatus, JobType

VALID_ID = "507f1f77bcf86cd799439011"


def _get_update_kwargs(mock_collection):
    args, _ = mock_collection.update_one.call_args
    return args[1]["$set"]


@pytest.fixture(autouse=True)
def mock_collection():
    with patch("app.infrastructure.tasks.helpers.get_knowledge_jobs_collection") as mock_get:
        coll = MagicMock()
        coll.insert_one = AsyncMock()
        coll.update_one = AsyncMock()
        mock_get.return_value = coll
        yield coll


@pytest.mark.asyncio
async def test_create_job(mock_collection):
    from app.infrastructure.tasks.helpers import create_job

    job = await create_job(
        job_type=JobType.DOCUMENT_PROCESSING,
        payload={"document_id": "doc-1"},
        store_id="store-1",
        organization_id="org-1",
        triggered_by="user-1",
        max_retries=5,
    )

    assert job.job_type == JobType.DOCUMENT_PROCESSING
    assert job.status == JobStatus.PENDING
    assert job.payload == {"document_id": "doc-1"}
    assert job.store_id == "store-1"
    assert job.organization_id == "org-1"
    assert job.triggered_by == "user-1"
    assert job.max_retries == 5
    assert job.id is not None
    assert job.progress == 0.0
    assert job.retry_count == 0
    assert job.celery_task_id is None

    mock_collection.insert_one.assert_awaited_once()
    inserted = mock_collection.insert_one.call_args[0][0]
    assert inserted["job_type"] == "document_processing"
    assert inserted["status"] == "pending"


@pytest.mark.asyncio
async def test_update_job_progress(mock_collection):
    from app.infrastructure.tasks.helpers import update_job_progress

    await update_job_progress(VALID_ID, 0.5, JobStatus.RUNNING)

    mock_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_job_progress_without_status(mock_collection):
    from app.infrastructure.tasks.helpers import update_job_progress

    await update_job_progress(VALID_ID, 0.8)

    mock_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_job(mock_collection):
    from app.infrastructure.tasks.helpers import complete_job

    await complete_job(VALID_ID, {"ok": True}, celery_task_id="celery-1")

    s = _get_update_kwargs(mock_collection)
    assert s["status"] == "completed"
    assert s["progress"] == 1.0
    assert s["result"] == {"ok": True}
    assert s["celery_task_id"] == "celery-1"


@pytest.mark.asyncio
async def test_complete_job_minimal(mock_collection):
    from app.infrastructure.tasks.helpers import complete_job

    await complete_job(VALID_ID)

    s = _get_update_kwargs(mock_collection)
    assert s["result"] == {}


@pytest.mark.asyncio
async def test_fail_job_dead_letter(mock_collection):
    from app.infrastructure.tasks.helpers import fail_job

    status = await fail_job(VALID_ID, "Fatal error", retry_count=3, max_retries=3)

    assert status == JobStatus.DEAD_LETTER

    s = _get_update_kwargs(mock_collection)
    assert s["status"] == "dead_letter"
    assert s["error_message"] == "Fatal error"


@pytest.mark.asyncio
async def test_fail_job_retrying(mock_collection):
    from app.infrastructure.tasks.helpers import fail_job

    status = await fail_job(VALID_ID, "Transient error", retry_count=1, max_retries=3)

    assert status == JobStatus.RETRYING
    s = _get_update_kwargs(mock_collection)
    assert s["status"] == "retrying"


@pytest.mark.asyncio
async def test_set_celery_task_id(mock_collection):
    from app.infrastructure.tasks.helpers import set_celery_task_id

    await set_celery_task_id(VALID_ID, "celery-task-abc")

    s = _get_update_kwargs(mock_collection)
    assert s["celery_task_id"] == "celery-task-abc"


@pytest.mark.asyncio
async def test_requeue_dead_letter(mock_collection):
    from app.infrastructure.tasks.helpers import requeue_dead_letter

    await requeue_dead_letter(VALID_ID)

    s = _get_update_kwargs(mock_collection)
    assert s["status"] == "pending"
    assert s["error_message"] is None
    assert s["retry_count"] == 0
    assert s["completed_at"] is None
