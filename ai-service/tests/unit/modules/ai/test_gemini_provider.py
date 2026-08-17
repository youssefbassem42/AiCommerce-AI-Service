from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.dto.ai_dto import ChatRequest, EmbeddingRequest, MessageDTO
from app.infrastructure.providers.gemini_provider import GeminiProvider


@pytest.fixture
def mock_genai_client():
    with patch("app.infrastructure.providers.gemini_provider.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_gemini_chat_success(mock_genai_client):
    provider = GeminiProvider(api_key="test-api-key")

    # Mock return value of client.aio.models.generate_content
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [MagicMock(text="Gemini text response", function_call=None)]

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = MagicMock(prompt_token_count=12, candidates_token_count=8, total_token_count=20)

    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[
            MessageDTO(role="system", content="You are a helper."),
            MessageDTO(role="user", content="Hello Gemini"),
        ],
        model="gemini-2.5-flash",
        temperature=0.7,
    )

    response = await provider.chat(request)

    assert response.provider == "gemini"
    assert response.model == "gemini-2.5-flash"
    assert response.message.content == "Gemini text response"
    assert response.usage.prompt_tokens == 12
    assert response.usage.completion_tokens == 8

    # Verify calls
    mock_genai_client.aio.models.generate_content.assert_called_once()
    call_kwargs = mock_genai_client.aio.models.generate_content.call_args[1]
    assert call_kwargs["model"] == "gemini-2.5-flash"
    assert call_kwargs["config"].temperature == 0.7
    assert call_kwargs["config"].system_instruction == "You are a helper."


@pytest.mark.asyncio
async def test_gemini_structured_output_generic_alias_uses_permissive_schema(mock_genai_client):
    from typing import Any

    provider = GeminiProvider(api_key="test-api-key")

    mock_candidate = MagicMock()
    mock_candidate.content.parts = [MagicMock(text='{"intent": "buy"}', function_call=None)]

    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = MagicMock(prompt_token_count=5, candidates_token_count=3, total_token_count=8)

    mock_genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    request = ChatRequest(messages=[MessageDTO(role="user", content="classify")], model="gemini-2.5-flash")

    response = await provider.structured_output(request, dict[str, Any])

    assert response.message.content == '{"intent": "buy"}'
    call_kwargs = mock_genai_client.aio.models.generate_content.call_args[1]
    assert call_kwargs["config"].response_schema == {"type": "object", "additionalProperties": True}


@pytest.mark.asyncio
async def test_gemini_embeddings(mock_genai_client):
    provider = GeminiProvider(api_key="test-api-key")

    # Mock return value of client.aio.models.embed_content
    mock_emb = MagicMock()
    mock_emb.values = [0.1, 0.2, 0.3]
    mock_response = MagicMock(embeddings=[mock_emb])

    mock_genai_client.aio.models.embed_content = AsyncMock(return_value=mock_response)

    request = EmbeddingRequest(input=["hello", "world"], model="gemini-embedding-001")

    response = await provider.embeddings(request)

    assert response.provider == "gemini"
    assert response.embeddings == [[0.1, 0.2, 0.3]]
    mock_genai_client.aio.models.embed_content.assert_called_once()
    call_kwargs = mock_genai_client.aio.models.embed_content.call_args[1]
    assert call_kwargs["model"] == "gemini-embedding-001"
    assert call_kwargs["contents"] == ["hello", "world"]
    assert call_kwargs["config"].output_dimensionality == 768
