import pytest
from app.infrastructure.providers.mock_provider import MockProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO, EmbeddingRequest


@pytest.mark.asyncio
async def test_mock_chat():
    provider = MockProvider()
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hello world")],
        model="mock-model",
    )
    response = await provider.chat(request)
    assert response.provider == "mock"
    assert "Hello world" in response.message.content


@pytest.mark.asyncio
async def test_mock_stream():
    provider = MockProvider()
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Hello")],
        model="mock-model",
    )
    chunks = []
    async for chunk in provider.stream(request):
        chunks.append(chunk)
    assert len(chunks) == 1
    assert chunks[0].provider == "mock"


@pytest.mark.asyncio
async def test_mock_embeddings():
    provider = MockProvider()
    request = EmbeddingRequest(input="test", model="mock-model")
    response = await provider.embeddings(request)
    assert response.provider == "mock"
    assert len(response.embeddings) == 1
    assert response.embeddings[0] == [0.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_mock_health_check():
    provider = MockProvider()
    health = await provider.health_check()
    assert health.status == "healthy"
    assert health.provider == "mock"


@pytest.mark.asyncio
async def test_mock_list_models():
    provider = MockProvider()
    models = await provider.list_models()
    assert models == ["mock-model"]


@pytest.mark.asyncio
async def test_mock_structured_output():
    provider = MockProvider()
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Test")],
        model="mock-model",
    )
    response = await provider.structured_output(request, {})
    assert response.provider == "mock"


@pytest.mark.asyncio
async def test_mock_tool_call():
    provider = MockProvider()
    request = ChatRequest(
        messages=[MessageDTO(role="user", content="Test")],
        model="mock-model",
    )
    response = await provider.tool_call(request)
    assert response.provider == "mock"
