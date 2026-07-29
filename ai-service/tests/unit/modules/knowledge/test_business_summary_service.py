import pytest
from unittest.mock import AsyncMock

from app.application.knowledge.services import BusinessSummaryService
from app.application.knowledge.dto import BusinessSummaryCreateDTO, BusinessSummaryUpdateDTO
from app.domain.knowledge.exceptions import BusinessSummaryNotFoundException


@pytest.mark.asyncio
async def test_create_summary(mock_summary_repo, sample_summary_create_dto, sample_summary_entity):
    mock_summary_repo.create = AsyncMock(return_value=sample_summary_entity)
    service = BusinessSummaryService(repository=mock_summary_repo)

    result = await service.create(sample_summary_create_dto)

    assert result.id == "summary-1"
    assert result.title == "Executive Summary"
    assert result.summary == "This is a business summary."
    mock_summary_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_summary_found(mock_summary_repo, sample_summary_entity):
    mock_summary_repo.find_by_id = AsyncMock(return_value=sample_summary_entity)
    service = BusinessSummaryService(repository=mock_summary_repo)

    result = await service.get_by_id("summary-1")

    assert result.id == "summary-1"
    assert result.document_id == "doc-1"
    mock_summary_repo.find_by_id.assert_awaited_once_with("summary-1")


@pytest.mark.asyncio
async def test_get_summary_not_found(mock_summary_repo):
    mock_summary_repo.find_by_id = AsyncMock(return_value=None)
    service = BusinessSummaryService(repository=mock_summary_repo)

    with pytest.raises(BusinessSummaryNotFoundException):
        await service.get_by_id("nonexistent")


@pytest.mark.asyncio
async def test_list_summaries(mock_summary_repo, sample_summary_entity):
    mock_summary_repo.paginate = AsyncMock(return_value=([sample_summary_entity], 1))
    service = BusinessSummaryService(repository=mock_summary_repo)

    result = await service.list(page=1, page_size=20, document_id="doc-1")

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].document_id == "doc-1"


@pytest.mark.asyncio
async def test_update_summary(mock_summary_repo, sample_summary_entity):
    mock_summary_repo.find_by_id = AsyncMock(return_value=sample_summary_entity)
    updated_entity = sample_summary_entity.model_copy()
    updated_entity.summary = "Updated summary text"
    mock_summary_repo.update = AsyncMock(return_value=updated_entity)
    service = BusinessSummaryService(repository=mock_summary_repo)

    result = await service.update("summary-1", BusinessSummaryUpdateDTO(summary="Updated summary text"))

    assert result.summary == "Updated summary text"
    mock_summary_repo.update.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_summary_not_found(mock_summary_repo):
    mock_summary_repo.find_by_id = AsyncMock(return_value=None)
    service = BusinessSummaryService(repository=mock_summary_repo)

    with pytest.raises(BusinessSummaryNotFoundException):
        await service.update("nonexistent", BusinessSummaryUpdateDTO(summary="New"))


@pytest.mark.asyncio
async def test_delete_summary(mock_summary_repo):
    mock_summary_repo.delete = AsyncMock(return_value=True)
    service = BusinessSummaryService(repository=mock_summary_repo)

    result = await service.delete("summary-1")
    assert result is True
    mock_summary_repo.delete.assert_awaited_once_with("summary-1")


@pytest.mark.asyncio
async def test_delete_summary_not_found(mock_summary_repo):
    mock_summary_repo.delete = AsyncMock(return_value=False)
    service = BusinessSummaryService(repository=mock_summary_repo)

    with pytest.raises(BusinessSummaryNotFoundException):
        await service.delete("nonexistent")
