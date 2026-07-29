import pytest
from unittest.mock import MagicMock, patch

from app.application.knowledge.services import (
    BusinessSummaryService,
    KnowledgeChunkService,
    KnowledgeDocumentService,
)


@patch("app.api.knowledge.dependencies.KnowledgeRepository", autospec=True)
def test_get_knowledge_repository(MockRepo):
    mock_instance = MagicMock()
    MockRepo.return_value = mock_instance

    from app.api.knowledge.dependencies import get_knowledge_repository
    repo = get_knowledge_repository()
    assert repo is mock_instance


@patch("app.api.knowledge.dependencies.ChunkRepository", autospec=True)
def test_get_chunk_repository(MockRepo):
    mock_instance = MagicMock()
    MockRepo.return_value = mock_instance

    from app.api.knowledge.dependencies import get_chunk_repository
    repo = get_chunk_repository()
    assert repo is mock_instance


@patch("app.api.knowledge.dependencies.BusinessSummaryRepository", autospec=True)
def test_get_business_summary_repository(MockRepo):
    mock_instance = MagicMock()
    MockRepo.return_value = mock_instance

    from app.api.knowledge.dependencies import get_business_summary_repository
    repo = get_business_summary_repository()
    assert repo is mock_instance


def test_get_knowledge_document_service():
    mock_repo = MagicMock()
    service = KnowledgeDocumentService(repository=mock_repo)
    assert isinstance(service, KnowledgeDocumentService)


def test_get_knowledge_chunk_service():
    mock_repo = MagicMock()
    service = KnowledgeChunkService(repository=mock_repo)
    assert isinstance(service, KnowledgeChunkService)


def test_get_business_summary_service():
    mock_repo = MagicMock()
    service = BusinessSummaryService(repository=mock_repo)
    assert isinstance(service, BusinessSummaryService)
