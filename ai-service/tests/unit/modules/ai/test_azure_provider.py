import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.azure_provider import AzureOpenAIProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO, EmbeddingRequest


@pytest.fixture
def mock_azure_client():
    with patch("app.infrastructure.providers.azure_provider.AsyncAzureOpenAI") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_azure_chat_success(mock_azure_client):
    provider = AzureOpenAIProvider(api_key="test-key", azure_endpoint="https://test.openai.azure.com", azure_deployment="gpt-4o")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Hello from Azure"
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="azure-1", model="gpt-4o", choices=[mock_choice], usage=mock_usage)

    mock_azure_client.chat.completions.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi Azure")],
        model="azure/gpt-4o",
    )

    response = await provider.chat(request)
    assert response.provider == "azure"
    assert response.message.content == "Hello from Azure"
    assert response.usage.prompt_tokens == 10


@pytest.mark.asyncio
async def test_azure_embeddings(mock_azure_client):
    provider = AzureOpenAIProvider(api_key="test-key", azure_endpoint="https://test.openai.azure.com", azure_deployment="text-embedding-3-small")

    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_usage = MagicMock(prompt_tokens=4)
    mock_response = MagicMock(data=[mock_data], model="text-embedding-3-small", usage=mock_usage)

    mock_azure_client.embeddings.create = AsyncMock(return_value=mock_response)

    request = EmbeddingRequest(input="test", model="text-embedding-3-small")
    response = await provider.embeddings(request)
    assert response.provider == "azure"
    assert len(response.embeddings) == 1


@pytest.mark.asyncio
async def test_azure_health_check(mock_azure_client):
    provider = AzureOpenAIProvider(api_key="test-key", azure_endpoint="https://test.openai.azure.com")
    mock_azure_client.models.list = AsyncMock(return_value=None)

    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "azure"


@pytest.mark.asyncio
async def test_azure_list_models():
    provider = AzureOpenAIProvider(api_key="test-key")
    models = await provider.list_models()
    assert len(models) > 0
    # Azure models in registry have name "gpt-4o" (key is "azure/gpt-4o")
    assert "gpt-4o" in models or "gpt-4o-mini" in models
