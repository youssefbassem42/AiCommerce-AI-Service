import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.deepseek_provider import DeepSeekProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO


@pytest.fixture
def mock_deepseek_client():
    with patch("app.infrastructure.providers.deepseek_provider.AsyncOpenAI") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_deepseek_chat_success(mock_deepseek_client):
    provider = DeepSeekProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Hello from DeepSeek"
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="ds-1", model="deepseek-chat", choices=[mock_choice], usage=mock_usage)

    mock_deepseek_client.chat.completions.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi")],
        model="deepseek-chat",
    )

    response = await provider.chat(request)
    assert response.provider == "deepseek"
    assert response.message.content == "Hello from DeepSeek"


@pytest.mark.asyncio
async def test_deepseek_health_check(mock_deepseek_client):
    provider = DeepSeekProvider(api_key="test-key")
    mock_deepseek_client.models.list = AsyncMock(return_value=None)

    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "deepseek"


@pytest.mark.asyncio
async def test_deepseek_embeddings_not_supported():
    provider = DeepSeekProvider(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await provider.embeddings(MagicMock())


@pytest.mark.asyncio
async def test_deepseek_structured_output(mock_deepseek_client):
    provider = DeepSeekProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = '{"result": "success"}'
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="struct-1", model="deepseek-chat", choices=[mock_choice], usage=mock_usage)

    mock_deepseek_client.chat.completions.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Give JSON")],
        model="deepseek-chat",
    )

    response = await provider.structured_output(request, {"type": "object"})
    assert response.message.content == '{"result": "success"}'
