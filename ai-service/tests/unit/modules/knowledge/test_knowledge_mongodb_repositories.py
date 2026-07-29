import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_mongo():
    """Mock MongoDB collection access for all tests in this module."""
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock()
    mock_collection.find = MagicMock()
    mock_collection.find.return_value.to_list = AsyncMock()
    mock_collection.insert_one = AsyncMock()
    mock_collection.replace_one = AsyncMock()
    mock_collection.delete_one = AsyncMock()
    mock_collection.count_documents = AsyncMock()
    mock_collection.aggregate = MagicMock()
    mock_collection.aggregate.return_value.to_list = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_collection

    targets = [
        "app.infrastructure.mongodb.repositories.knowledge_repository.get_knowledge_documents_collection",
        "app.infrastructure.mongodb.repositories.knowledge_repository.get_knowledge_chunks_collection",
        "app.infrastructure.mongodb.repositories.chunk_repository.get_knowledge_chunks_collection",
        "app.infrastructure.mongodb.repositories.business_summary_repository.get_knowledge_business_summaries_collection",
    ]
    with (
        patch(targets[0], return_value=mock_collection),
        patch(targets[1], return_value=mock_collection),
        patch(targets[2], return_value=mock_collection),
        patch(targets[3], return_value=mock_collection),
        patch("app.infrastructure.mongodb.client.get_mongodb", return_value=mock_db),
    ):
        yield mock_collection


@pytest.mark.asyncio
async def test_knowledge_repository_find_by_store_id(mock_mongo):
    from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository

    mock_mongo.find.return_value.to_list = AsyncMock(return_value=[])
    mock_mongo.count_documents = AsyncMock(return_value=0)

    repo = KnowledgeRepository()
    results = await repo.find_by_store_id("store-1")

    assert results == []


@pytest.mark.asyncio
async def test_knowledge_repository_find_by_status(mock_mongo):
    from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository

    mock_mongo.find.return_value.to_list = AsyncMock(return_value=[])
    mock_mongo.count_documents = AsyncMock(return_value=0)

    repo = KnowledgeRepository()
    results = await repo.find_by_status("active")

    assert results == []


@pytest.mark.asyncio
async def test_chunk_repository_find_by_document_id(mock_mongo):
    from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository

    mock_mongo.find.return_value.to_list = AsyncMock(return_value=[])
    mock_mongo.count_documents = AsyncMock(return_value=0)

    repo = ChunkRepository()
    results = await repo.find_by_document_id("doc-1")

    assert results == []


@pytest.mark.asyncio
async def test_chunk_repository_find_by_document_id_with_version(mock_mongo):
    from app.infrastructure.mongodb.repositories.chunk_repository import ChunkRepository

    mock_mongo.find.return_value.to_list = AsyncMock(return_value=[])
    mock_mongo.count_documents = AsyncMock(return_value=0)

    repo = ChunkRepository()
    results = await repo.find_by_document_id("doc-1", version_number=2)

    assert results == []


@pytest.mark.asyncio
async def test_business_summary_repository_find_by_document_id(mock_mongo):
    from app.infrastructure.mongodb.repositories.business_summary_repository import BusinessSummaryRepository

    mock_mongo.find.return_value.to_list = AsyncMock(return_value=[])
    mock_mongo.count_documents = AsyncMock(return_value=0)

    repo = BusinessSummaryRepository()
    results = await repo.find_by_document_id("doc-1")

    assert results == []
