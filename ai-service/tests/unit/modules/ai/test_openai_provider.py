import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO, EmbeddingRequest


@pytest.fixture
def mock_openai_client():
    with patch("app.infrastructure.providers.openai_provider.AsyncOpenAI") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_openai_chat_success(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = "Hello from OpenAI"
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="chat-1", model="gpt-4o-mini", choices=[mock_choice], usage=mock_usage)

    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi")],
        model="gpt-4o-mini",
        temperature=0.7,
    )

    response = await provider.chat(request)
    assert response.provider == "openai"
    assert response.message.content == "Hello from OpenAI"
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5


@pytest.mark.asyncio
async def test_openai_embeddings(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")

    mock_data = MagicMock()
    mock_data.embedding = [0.1, 0.2, 0.3]
    mock_usage = MagicMock(prompt_tokens=4)
    mock_response = MagicMock(data=[mock_data], model="text-embedding-3-small", usage=mock_usage)

    mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

    request = EmbeddingRequest(input="test text", model="text-embedding-3-small")
    response = await provider.embeddings(request)
    assert response.provider == "openai"
    assert len(response.embeddings) == 1


@pytest.mark.asyncio
async def test_openai_stream(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")

    chunk1 = MagicMock()
    chunk1.id = "chunk-1"
    chunk1.model = "gpt-4o-mini"
    chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"), finish_reason=None)]
    chunk1.usage = None

    chunk2 = MagicMock()
    chunk2.id = "chunk-2"
    chunk2.model = "gpt-4o-mini"
    chunk2.choices = [MagicMock(delta=MagicMock(content=" world"), finish_reason="stop")]
    chunk2.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)

    async def mock_stream():
        yield chunk1
        yield chunk2

    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_stream())

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi")],
        model="gpt-4o-mini",
    )

    chunks = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert chunks[0].content == "Hello"
    assert chunks[1].content == " world"


@pytest.mark.asyncio
async def test_openai_health_check(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")
    mock_openai_client.models.list = AsyncMock(return_value=None)

    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "openai"


@pytest.mark.asyncio
async def test_openai_list_models():
    provider = OpenAIProvider(api_key="test-key")
    models = await provider.list_models()
    assert len(models) > 0
    assert "gpt-4o" in models


@pytest.mark.asyncio
async def test_openai_structured_output(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = '{"name": "test"}'
    mock_choice.message.tool_calls = None

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="struct-1", model="gpt-4o-mini", choices=[mock_choice], usage=mock_usage)

    mock_openai_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Give me JSON")],
        model="gpt-4o-mini",
    )

    response = await provider.structured_output(request, {"type": "json_object"})
    assert response.message.content == '{"name": "test"}'


@pytest.mark.asyncio
async def test_openai_tool_call(mock_openai_client):
    provider = OpenAIProvider(api_key="test-key")

    mock_tool = MagicMock()
    mock_tool.id = "call-1"
    mock_tool.type = "function"
    mock_tool.function.name = "get_weather"
    mock_tool.function.arguments = '{"location": "NYC"}'

    mock_choice = MagicMock()
    mock_choice.message.role = "assistant"
    mock_choice.message.content = ""
    mock_choice.message.tool_calls = [mock_tool]

    mock_usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    mock_response = MagicMock(id="tool-1", model="gpt-4o-mini", choices=[mock_choice], usage=mock_usage)

    mock_openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Weather?")],
        model="gpt-4o-mini",
    )

    response = await provider.tool_call(request)
    assert response.message.tool_calls is not None
    assert response.message.tool_calls[0].function_name == "get_weather"
