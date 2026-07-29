import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.mistral_provider import MistralProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO, EmbeddingRequest


@pytest.fixture
def mock_mistral_client():
    with patch("app.infrastructure.providers.mistral_provider.Mistral") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_mistral_chat_success(mock_mistral_client):
    provider = MistralProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Hello from Mistral"
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="mistral-1", model="mistral-large-latest", choices=[mock_choice], usage=mock_usage)

    mock_mistral_client.chat.complete_async = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi")],
        model="mistral-large-latest",
    )

    response = await provider.chat(request)
    assert response.provider == "mistral"
    assert response.message.content == "Hello from Mistral"


@pytest.mark.asyncio
async def test_mistral_embeddings(mock_mistral_client):
    provider = MistralProvider(api_key="test-key")

    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_usage = MagicMock(prompt_tokens=4)
    mock_response = MagicMock(data=[mock_data], model="mistral-embed", usage=mock_usage)

    mock_mistral_client.embeddings.create_async = AsyncMock(return_value=mock_response)

    request = EmbeddingRequest(input="test", model="mistral-embed")
    response = await provider.embeddings(request)
    assert response.provider == "mistral"
    assert len(response.embeddings) == 1


@pytest.mark.asyncio
async def test_mistral_health_check(mock_mistral_client):
    provider = MistralProvider(api_key="test-key")
    mock_mistral_client.models.list_async = AsyncMock(return_value=None)

    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "mistral"


@pytest.mark.asyncio
async def test_mistral_list_models():
    provider = MistralProvider(api_key="test-key")
    models = await provider.list_models()
    assert len(models) > 0
    assert "mistral-large-latest" in models
