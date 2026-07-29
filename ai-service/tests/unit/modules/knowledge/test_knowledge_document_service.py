import pytest
from unittest.mock import AsyncMock

from app.application.knowledge.services import KnowledgeDocumentService
from app.application.knowledge.dto import KnowledgeDocumentCreateDTO, KnowledgeDocumentUpdateDTO
from app.domain.knowledge.exceptions import KnowledgeDocumentNotFoundException


@pytest.mark.asyncio
async def test_create_document(mock_knowledge_repo, sample_document_create_dto, sample_document_entity):
    mock_knowledge_repo.create = AsyncMock(return_value=sample_document_entity)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    result = await service.create(sample_document_create_dto)

    assert result.id == "doc-1"
    assert result.title == "Test Document"
    assert result.store_id == "store-1"
    mock_knowledge_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_found(mock_knowledge_repo, sample_document_entity):
    mock_knowledge_repo.find_by_id = AsyncMock(return_value=sample_document_entity)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    result = await service.get_by_id("doc-1")

    assert result.id == "doc-1"
    assert result.title == "Test Document"
    mock_knowledge_repo.find_by_id.assert_awaited_once_with("doc-1")


@pytest.mark.asyncio
async def test_get_document_not_found(mock_knowledge_repo):
    mock_knowledge_repo.find_by_id = AsyncMock(return_value=None)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    with pytest.raises(KnowledgeDocumentNotFoundException):
        await service.get_by_id("nonexistent")


@pytest.mark.asyncio
async def test_list_documents(mock_knowledge_repo, sample_document_entity):
    mock_knowledge_repo.paginate = AsyncMock(return_value=([sample_document_entity], 1))
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    result = await service.list(page=1, page_size=20, store_id="store-1")

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].id == "doc-1"
    mock_knowledge_repo.paginate.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_document(mock_knowledge_repo, sample_document_entity):
    mock_knowledge_repo.find_by_id = AsyncMock(return_value=sample_document_entity)
    updated_entity = sample_document_entity.model_copy()
    updated_entity.title = "Updated Title"
    mock_knowledge_repo.update = AsyncMock(return_value=updated_entity)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    result = await service.update("doc-1", KnowledgeDocumentUpdateDTO(title="Updated Title"))

    assert result.title == "Updated Title"
    mock_knowledge_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_document_not_found(mock_knowledge_repo):
    mock_knowledge_repo.find_by_id = AsyncMock(return_value=None)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    with pytest.raises(KnowledgeDocumentNotFoundException):
        await service.update("nonexistent", KnowledgeDocumentUpdateDTO(title="New Title"))


@pytest.mark.asyncio
async def test_delete_document(mock_knowledge_repo):
    mock_knowledge_repo.delete = AsyncMock(return_value=True)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    result = await service.delete("doc-1")
    assert result is True
    mock_knowledge_repo.delete.assert_awaited_once_with("doc-1")


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_knowledge_repo):
    mock_knowledge_repo.delete = AsyncMock(return_value=False)
    service = KnowledgeDocumentService(repository=mock_knowledge_repo)

    with pytest.raises(KnowledgeDocumentNotFoundException):
        await service.delete("nonexistent")
