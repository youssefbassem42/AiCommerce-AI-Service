from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.application.services.chat_service import ChatService
from app.core.ai_exceptions import AIException, ProviderUnavailableException, RateLimitException


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat = AsyncMock()
    provider.stream = AsyncMock()
    return provider


@pytest.fixture
def mock_factory(mock_provider):
    factory = MagicMock()
    factory.get_provider.return_value = mock_provider
    return factory


@pytest.fixture
def chat_service(mock_factory):
    return ChatService(provider_factory=mock_factory)


class TestChatServiceEdgeCases:
    async def test_empty_messages_list(self, chat_service, mock_provider):
        mock_provider.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content=""),
            usage=UsageDTO(), latency_ms=0,
        )
        request = ChatRequest(messages=[], model="gpt-4o-mini")
        response = await chat_service.chat(request)
        assert response.message.content == ""

    async def test_all_providers_fail(self, chat_service, mock_provider):
        mock_provider.chat.side_effect = ProviderUnavailableException("openai", "All providers down")
        request = ChatRequest(
            messages=[MessageDTO(role="user", content="hello")],
            model="gpt-4o-mini",
        )
        with pytest.raises(AIException):
            await chat_service.chat(request)

    async def test_rate_limit_then_succeed_on_fallback(self, mock_factory):
        primary = AsyncMock()
        primary.chat.side_effect = RateLimitException("openai", "Rate limited")
        fallback = AsyncMock()
        fallback.chat.return_value = ChatResponse(
            id="fb", model="claude-3", provider="anthropic",
            message=MessageDTO(role="assistant", content="fallback response"),
            usage=UsageDTO(), latency_ms=0,
        )

        def get_provider(name):
            return {"openai": primary, "anthropic": fallback}.get(name, primary)

        mock_factory.get_provider.side_effect = get_provider
        service = ChatService(provider_factory=mock_factory)
        request = ChatRequest(
            messages=[MessageDTO(role="user", content="hello")],
            model="gpt-4o-mini",
        )
        response = await service.chat(request, fallbacks=["anthropic"])
        assert response.message.content == "fallback response"

    async def test_all_fallbacks_exhausted(self, mock_factory):
        primary = AsyncMock()
        primary.chat.side_effect = ProviderUnavailableException("openai", "Primary down")
        fallback = AsyncMock()
        fallback.chat.side_effect = ProviderUnavailableException("anthropic", "Fallback down")

        def get_provider(name):
            return {"openai": primary, "anthropic": fallback}.get(name, primary)

        mock_factory.get_provider.side_effect = get_provider
        service = ChatService(provider_factory=mock_factory)
        request = ChatRequest(
            messages=[MessageDTO(role="user", content="hello")],
            model="gpt-4o-mini",
        )
        with pytest.raises(AIException, match="currently unavailable"):
            await service.chat(request, fallbacks=["anthropic"])

    async def test_stream_not_supported(self, chat_service, mock_provider):
        from app.application.dto.ai_dto import ChatRequest
        from app.core.model_registry import ModelRegistry

        request = ChatRequest(
            messages=[MessageDTO(role="user", content="hello")],
            model="gpt-4o-mini", stream=True,
        )
        mock_provider.chat.side_effect = AIException("Streaming not supported", 400)
        with pytest.raises(AIException):
            await chat_service.chat(request)

    async def test_empty_content_in_response(self, chat_service, mock_provider):
        mock_provider.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content=""),
            usage=UsageDTO(), latency_ms=0,
        )
        request = ChatRequest(
            messages=[MessageDTO(role="user", content="say nothing")],
            model="gpt-4o-mini",
        )
        response = await chat_service.chat(request)
        assert response.message.content == ""

    async def test_content_as_list(self, chat_service, mock_provider):
        mock_provider.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content=["part1", "part2"]),
            usage=UsageDTO(), latency_ms=0,
        )
        request = ChatRequest(
            messages=[MessageDTO(role="user", content="list response")],
            model="gpt-4o-mini",
        )
        response = await chat_service.chat(request)
        assert isinstance(response.message.content, list)

    async def test_no_user_message_in_history(self, chat_service, mock_provider):
        mock_provider.chat.return_value = ChatResponse(
            id="test", model="gpt-4o-mini", provider="openai",
            message=MessageDTO(role="assistant", content="response"),
            usage=UsageDTO(), latency_ms=0,
        )
        request = ChatRequest(
            messages=[MessageDTO(role="system", content="be helpful")],
            model="gpt-4o-mini",
        )
        response = await chat_service.chat(request, conversation_id="conv_1")
        assert response.message.content == "response"

    async def test_embeddings_failure(self, chat_service, mock_provider):
        from app.application.dto.ai_dto import EmbeddingRequest
        mock_provider.embeddings.side_effect = RuntimeError("Embedding service down")
        request = EmbeddingRequest(input="test", model="text-embedding-3-small")
        with pytest.raises(RuntimeError):
            await chat_service.embeddings(request)

    async def test_structured_output_failure(self, chat_service, mock_provider):
        mock_provider.structured_output.side_effect = RuntimeError("Structured output failed")
        chat_req = ChatRequest(
            messages=[MessageDTO(role="user", content="extract data")],
            model="gpt-4o-mini",
        )
        with pytest.raises(RuntimeError):
            await chat_service.structured_output(chat_req, {})
