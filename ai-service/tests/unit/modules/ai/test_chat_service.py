import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.application.services.chat_service import ChatService
from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.core.ai_exceptions import ProviderUnavailableException, AIException

@pytest.mark.asyncio
async def test_chat_service_success():
    # Setup mocks
    mock_factory = MagicMock()
    mock_provider = AsyncMock()
    
    mock_response = ChatResponse(
        id="test-id",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(role="assistant", content="Test response"),
        usage=UsageDTO(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.01),
        latency_ms=10.0
    )
    mock_provider.chat.return_value = mock_response
    mock_factory.get_provider.return_value = mock_provider
    
    chat_service = ChatService(provider_factory=mock_factory)
    
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hello")],
        model="gpt-4o-mini"
    )
    
    response = await chat_service.chat(request)
    
    assert response.id == "test-id"
    assert response.message.content == "Test response"
    mock_factory.get_provider.assert_called_once_with("openai")
    mock_provider.chat.assert_called_once()


@pytest.mark.asyncio
async def test_chat_service_fallback():
    # Setup mocks
    mock_factory = MagicMock()
    
    mock_failing_provider = AsyncMock()
    mock_failing_provider.chat.side_effect = ProviderUnavailableException("openai", "Connection refused")
    
    mock_success_provider = AsyncMock()
    mock_response = ChatResponse(
        id="fallback-id",
        model="gpt-4o-mini",
        provider="gemini",
        message=MessageDTO(role="assistant", content="Fallback response"),
        usage=UsageDTO(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.01),
        latency_ms=10.0
    )
    mock_success_provider.chat.return_value = mock_response
    
    def get_provider_side_effect(name):
        if name == "openai":
            return mock_failing_provider
        if name == "gemini":
            return mock_success_provider
        return None
        
    mock_factory.get_provider.side_effect = get_provider_side_effect
    
    chat_service = ChatService(provider_factory=mock_factory)
    
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hello")],
        model="gpt-4o-mini"
    )
    
    # We specify gemini as fallback
    response = await chat_service.chat(request, fallbacks=["gemini"])
    
    assert response.id == "fallback-id"
    assert response.provider == "gemini"
    assert response.message.content == "Fallback response"
    
    # Both providers should have been retrieved
    mock_failing_provider.chat.assert_called_once()
    mock_success_provider.chat.assert_called_once()
