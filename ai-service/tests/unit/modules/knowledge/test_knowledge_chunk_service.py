import pytest
from unittest.mock import AsyncMock

from app.application.knowledge.services import KnowledgeChunkService
from app.application.knowledge.dto import KnowledgeChunkCreateDTO, KnowledgeChunkUpdateDTO
from app.domain.knowledge.exceptions import KnowledgeChunkNotFoundException


@pytest.mark.asyncio
async def test_create_chunk(mock_chunk_repo, sample_chunk_create_dto, sample_chunk_entity):
    mock_chunk_repo.create = AsyncMock(return_value=sample_chunk_entity)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    result = await service.create(sample_chunk_create_dto)

    assert result.id == "chunk-1"
    assert result.content == "This is the first chunk content."
    assert result.chunk_index == 0
    mock_chunk_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_chunk_found(mock_chunk_repo, sample_chunk_entity):
    mock_chunk_repo.find_by_id = AsyncMock(return_value=sample_chunk_entity)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    result = await service.get_by_id("chunk-1")

    assert result.id == "chunk-1"
    assert result.document_id == "doc-1"
    mock_chunk_repo.find_by_id.assert_awaited_once_with("chunk-1")


@pytest.mark.asyncio
async def test_get_chunk_not_found(mock_chunk_repo):
    mock_chunk_repo.find_by_id = AsyncMock(return_value=None)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    with pytest.raises(KnowledgeChunkNotFoundException):
        await service.get_by_id("nonexistent")


@pytest.mark.asyncio
async def test_list_chunks(mock_chunk_repo, sample_chunk_entity):
    mock_chunk_repo.paginate = AsyncMock(return_value=([sample_chunk_entity], 1))
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    result = await service.list(page=1, page_size=20, document_id="doc-1")

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].document_id == "doc-1"


@pytest.mark.asyncio
async def test_update_chunk(mock_chunk_repo, sample_chunk_entity):
    mock_chunk_repo.find_by_id = AsyncMock(return_value=sample_chunk_entity)
    updated_entity = sample_chunk_entity.model_copy()
    updated_entity.content = "Updated content"
    mock_chunk_repo.update = AsyncMock(return_value=updated_entity)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    result = await service.update("chunk-1", KnowledgeChunkUpdateDTO(content="Updated content"))

    assert result.content == "Updated content"
    mock_chunk_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_chunk_not_found(mock_chunk_repo):
    mock_chunk_repo.find_by_id = AsyncMock(return_value=None)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    with pytest.raises(KnowledgeChunkNotFoundException):
        await service.update("nonexistent", KnowledgeChunkUpdateDTO(content="New"))


@pytest.mark.asyncio
async def test_delete_chunk(mock_chunk_repo):
    mock_chunk_repo.delete = AsyncMock(return_value=True)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    result = await service.delete("chunk-1")
    assert result is True
    mock_chunk_repo.delete.assert_awaited_once_with("chunk-1")


@pytest.mark.asyncio
async def test_delete_chunk_not_found(mock_chunk_repo):
    mock_chunk_repo.delete = AsyncMock(return_value=False)
    service = KnowledgeChunkService(repository=mock_chunk_repo)

    with pytest.raises(KnowledgeChunkNotFoundException):
        await service.delete("nonexistent")
