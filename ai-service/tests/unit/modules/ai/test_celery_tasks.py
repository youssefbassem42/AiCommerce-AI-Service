import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.tasks.celery_tasks import (
    generate_embeddings_task,
    summarize_conversation_task
)
from app.application.dto.ai_dto import EmbeddingResponse, ChatResponse, MessageDTO, UsageDTO

@patch("app.infrastructure.tasks.celery_tasks.LLMProviderFactory")
def test_generate_embeddings_task(mock_factory_cls):
    # Setup mocks
    mock_factory = MagicMock()
    mock_provider = AsyncMock()
    mock_factory.get_provider.return_value = mock_provider
    mock_factory_cls.return_value = mock_factory
    
    mock_response = EmbeddingResponse(
        model="gemini-embedding-001",
        provider="gemini",
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        usage=UsageDTO()
    )
    mock_provider.embeddings.return_value = mock_response
    
    # Run task
    result = generate_embeddings_task(texts=["hello", "world"], model="gemini-embedding-001")
    
    # Assertions
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_factory.get_provider.assert_called_once_with("gemini")
    mock_provider.embeddings.assert_called_once()

@patch("app.infrastructure.tasks.celery_tasks.ConversationRepository")
@patch("app.infrastructure.tasks.celery_tasks.LLMProviderFactory")
def test_summarize_conversation_task(mock_factory_cls, mock_repo_cls):
    # Setup mocks
    mock_repo = MagicMock()
    mock_repo.get_conversation = AsyncMock(return_value={
        "conversation_id": "conv-123",
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "How can I help you today?"}
        ],
        "metadata": {}
    })
    mock_repo.collection = MagicMock()
    mock_repo.collection.update_one = AsyncMock()
    mock_repo_cls.return_value = mock_repo
    
    mock_factory = MagicMock()
    mock_provider = AsyncMock()
    mock_response = ChatResponse(
        id="test-chat",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(role="assistant", content="This is a summary."),
        usage=UsageDTO(),
        latency_ms=50.0
    )
    mock_provider.chat.return_value = mock_response
    mock_factory.get_provider.return_value = mock_provider
    mock_factory_cls.return_value = mock_factory
    
    # Run task
    result = summarize_conversation_task(conversation_id="conv-123", model="gpt-4o-mini")
    
    # Assertions
    assert result == "This is a summary."
    mock_repo.get_conversation.assert_called_once_with("conv-123")
    mock_repo.collection.update_one.assert_called_once()
    mock_provider.chat.assert_called_once()
