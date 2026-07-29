import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import bson

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.value_objects import JobStatus, JobType

VALID_ID = "507f1f77bcf86cd799439011"


@pytest.fixture(autouse=True)
def mock_jobs_collection():
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock()
    mock_collection.find = MagicMock()
    mock_collection.find.return_value.to_list = AsyncMock(return_value=[])
    mock_collection.insert_one = AsyncMock()
    mock_collection.replace_one = AsyncMock()
    mock_collection.delete_one = AsyncMock()
    mock_collection.count_documents = AsyncMock(return_value=0)
    mock_collection.update_one = AsyncMock()
    mock_collection.insert_many = AsyncMock()

    with patch(
        "app.infrastructure.mongodb.repositories.job_repository.get_knowledge_jobs_collection",
        return_value=mock_collection,
    ):
        yield mock_collection


@pytest.fixture
def sample_job():
    return KnowledgeJob(
        id=VALID_ID,
        job_type=JobType.DOCUMENT_PROCESSING,
        status=JobStatus.PENDING,
        payload={"document_id": "doc-1"},
        store_id="store-1",
        organization_id="org-1",
        max_retries=3,
    )


@pytest.mark.asyncio
async def test_create_job(mock_jobs_collection, sample_job):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.insert_one = AsyncMock()

    repo = JobRepository()
    result = await repo.create(sample_job)

    assert result.id == sample_job.id
    mock_jobs_collection.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_by_id_found(mock_jobs_collection, sample_job):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository
    from app.infrastructure.mongodb.documents.job_document import KnowledgeJobDocument

    doc = KnowledgeJobDocument.from_entity(sample_job)
    mock_jobs_collection.find_one.return_value = doc.to_mongo_dict()

    repo = JobRepository()
    result = await repo.find_by_id(sample_job.id)

    assert result is not None
    assert result.id == sample_job.id
    assert result.job_type == JobType.DOCUMENT_PROCESSING


@pytest.mark.asyncio
async def test_find_by_id_not_found(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.find_one.return_value = None

    repo = JobRepository()
    result = await repo.find_by_id("000000000000000000000000")

    assert result is None


@pytest.mark.asyncio
async def test_find_by_status(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.find.return_value.to_list = AsyncMock(return_value=[])

    repo = JobRepository()
    results = await repo.find_by_status(JobStatus.PENDING)

    assert results == []


@pytest.mark.asyncio
async def test_find_by_type_and_status(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.find.return_value.to_list = AsyncMock(return_value=[])

    repo = JobRepository()
    results = await repo.find_by_type_and_status(JobType.DOCUMENT_PROCESSING, JobStatus.FAILED)

    assert results == []


@pytest.mark.asyncio
async def test_find_dead_letters(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.find.return_value.to_list = AsyncMock(return_value=[])

    repo = JobRepository()
    results = await repo.find_dead_letters()

    assert results == []


@pytest.mark.asyncio
async def test_update_progress(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    repo = JobRepository()
    await repo.update_progress(VALID_ID, 0.5, JobStatus.RUNNING)

    mock_jobs_collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_mark_completed(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    repo = JobRepository()
    await repo.mark_completed(VALID_ID, {"ok": True})

    args, _ = mock_jobs_collection.update_one.call_args
    update_dict = args[1]["$set"]
    assert update_dict["status"] == JobStatus.COMPLETED.value
    assert update_dict["progress"] == 1.0
    assert update_dict["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_mark_failed(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    repo = JobRepository()
    await repo.mark_failed(VALID_ID, "Something went wrong")

    args, _ = mock_jobs_collection.update_one.call_args
    update_dict = args[1]["$set"]
    assert update_dict["status"] == JobStatus.FAILED.value
    assert update_dict["error_message"] == "Something went wrong"


@pytest.mark.asyncio
async def test_update(mock_jobs_collection, sample_job):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.replace_one = AsyncMock()

    repo = JobRepository()
    result = await repo.update(sample_job)

    assert result.id == sample_job.id
    mock_jobs_collection.replace_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_existing(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_delete_result = MagicMock()
    mock_delete_result.deleted_count = 1
    mock_jobs_collection.delete_one = AsyncMock(return_value=mock_delete_result)

    repo = JobRepository()
    result = await repo.delete(VALID_ID)

    assert result is True


@pytest.mark.asyncio
async def test_delete_not_found(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_delete_result = MagicMock()
    mock_delete_result.deleted_count = 0
    mock_jobs_collection.delete_one = AsyncMock(return_value=mock_delete_result)

    repo = JobRepository()
    result = await repo.delete("000000000000000000000000")

    assert result is False


@pytest.mark.asyncio
async def test_paginate(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.count_documents = AsyncMock(return_value=0)
    mock_jobs_collection.find.return_value.to_list = AsyncMock(return_value=[])

    repo = JobRepository()
    items, total = await repo.paginate({}, page=1, page_size=20)

    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_exists_true(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.count_documents = AsyncMock(return_value=1)

    repo = JobRepository()
    result = await repo.exists(VALID_ID)

    assert result is True


@pytest.mark.asyncio
async def test_exists_false(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.count_documents = AsyncMock(return_value=0)

    repo = JobRepository()
    result = await repo.exists("000000000000000000000000")

    assert result is False


@pytest.mark.asyncio
async def test_bulk_insert_empty(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    repo = JobRepository()
    result = await repo.bulk_insert([])

    assert result == 0


@pytest.mark.asyncio
async def test_bulk_insert_non_empty(mock_jobs_collection, sample_job):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_insert_result = MagicMock()
    mock_insert_result.inserted_ids = ["id1"]
    mock_jobs_collection.insert_many = AsyncMock(return_value=mock_insert_result)

    repo = JobRepository()
    result = await repo.bulk_insert([sample_job])

    assert result == 1


@pytest.mark.asyncio
async def test_bulk_update(mock_jobs_collection, sample_job):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.replace_one = AsyncMock()

    repo = JobRepository()
    result = await repo.bulk_update([sample_job])

    assert result == 1
    mock_jobs_collection.replace_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_many(mock_jobs_collection):
    from app.infrastructure.mongodb.repositories.job_repository import JobRepository

    mock_jobs_collection.find.return_value.to_list = AsyncMock(return_value=[])

    repo = JobRepository()
    results = await repo.find_many({"status": "pending"})

    assert results == []
