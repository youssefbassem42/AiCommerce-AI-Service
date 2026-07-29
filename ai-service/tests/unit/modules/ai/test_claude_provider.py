import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.claude_provider import ClaudeProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO


@pytest.fixture
def mock_claude_client():
    with patch("app.infrastructure.providers.claude_provider.AsyncAnthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.mark.asyncio
async def test_claude_chat_success(mock_claude_client):
    provider = ClaudeProvider(api_key="test-key")

    mock_block = MagicMock()
    mock_block.type = "text"
    mock_block.text = "Hello from Claude"

    mock_usage = MagicMock(input_tokens=15, output_tokens=10)
    mock_response = MagicMock(
        id="msg-1",
        model="claude-3-5-sonnet-latest",
        content=[mock_block],
        usage=mock_usage,
        stop_reason="end_turn",
    )

    mock_claude_client.messages.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hi Claude")],
        model="claude-3-5-sonnet-latest",
    )

    response = await provider.chat(request)
    assert response.provider == "claude"
    assert response.message.content == "Hello from Claude"
    assert response.usage.prompt_tokens == 15
    assert response.usage.completion_tokens == 10


@pytest.mark.asyncio
async def test_claude_health_check(mock_claude_client):
    provider = ClaudeProvider(api_key="test-key")
    mock_response = MagicMock()
    mock_response.id = "health-1"
    mock_claude_client.messages.create = AsyncMock(return_value=mock_response)

    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "claude"


@pytest.mark.asyncio
async def test_claude_list_models():
    provider = ClaudeProvider(api_key="test-key")
    models = await provider.list_models()
    assert len(models) > 0
    assert "claude-3-5-sonnet-latest" in models


@pytest.mark.asyncio
async def test_claude_structured_output(mock_claude_client):
    provider = ClaudeProvider(api_key="test-key")

    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = "structured_output_schema"  # matches default schema_name in Claude provider
    mock_block.input = {"name": "test", "value": 42}

    mock_usage = MagicMock(input_tokens=20, output_tokens=15)
    mock_response = MagicMock(
        id="struct-1",
        model="claude-3-5-sonnet-latest",
        content=[mock_block],
        usage=mock_usage,
    )

    mock_claude_client.messages.create = AsyncMock(return_value=mock_response)

    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Give structured output")],
        model="claude-3-5-sonnet-latest",
    )

    response = await provider.structured_output(request, {"type": "object", "properties": {"name": {"type": "string"}}})
    assert response.provider == "claude"
    assert '"name"' in response.message.content or "name" in response.message.content


@pytest.mark.asyncio
async def test_claude_embeddings_not_supported():
    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await provider.embeddings(MagicMock())
