import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from app.infrastructure.providers.ollama_provider import OllamaProvider
from app.application.dto.ai_dto import ChatRequest, MessageDTO, EmbeddingRequest


@pytest.mark.asyncio
async def test_ollama_chat_success():
    provider = OllamaProvider(base_url="http://localhost:11434")

    mock_response_data = {
        "model": "llama3",
        "message": {"role": "assistant", "content": "Hello from Ollama"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_response_data)
        mock_client.post = AsyncMock(return_value=mock_response)

        request = ChatRequest(
            messages=[MessageDTO(role="user", content="Hi")],
            model="llama3",
        )

        response = await provider.chat(request)
        assert response.provider == "ollama"
        assert response.message.content == "Hello from Ollama"
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5


@pytest.mark.asyncio
async def test_ollama_embeddings():
    provider = OllamaProvider(base_url="http://localhost:11434")

    mock_response_data = {"embedding": [0.1, 0.2, 0.3]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_response_data)
        mock_client.post = AsyncMock(return_value=mock_response)

        request = EmbeddingRequest(input="test text", model="nomic-embed-text")
        response = await provider.embeddings(request)
        assert response.provider == "ollama"
        assert len(response.embeddings) == 1
        assert response.embeddings[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_ollama_health_check():
    provider = OllamaProvider(base_url="http://localhost:11434")

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)

        health = await provider.health_check()
        assert health.status == "healthy"
        assert health.provider == "ollama"


@pytest.mark.asyncio
async def test_ollama_list_models():
    provider = OllamaProvider(base_url="http://localhost:11434")

    mock_response_data = {"models": [{"name": "llama3"}, {"name": "mistral"}]}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value=mock_response_data)
        mock_client.get = AsyncMock(return_value=mock_response)

        models = await provider.list_models()
        assert "llama3" in models
        assert "mistral" in models


@pytest.mark.asyncio
async def test_ollama_stream():
    provider = OllamaProvider(base_url="http://localhost:11434")

    mock_lines = [
        '{"model":"llama3","message":{"role":"assistant","content":"Hello"},"done":false}',
        '{"model":"llama3","message":{"role":"assistant","content":" world"},"done":false}',
        '{"model":"llama3","message":{"role":"assistant","content":""},"done":true,"prompt_eval_count":5,"eval_count":8}',
    ]

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        async def mock_aiter_lines():
            for line in mock_lines:
                yield line

        mock_stream = MagicMock()
        mock_stream.__aenter__.return_value = mock_stream
        mock_stream.aiter_lines = mock_aiter_lines
        mock_client.stream = MagicMock(return_value=mock_stream)

        request = ChatRequest(
            messages=[MessageDTO(role="user", content="Hi")],
            model="llama3",
        )

        chunks = []
        async for chunk in provider.stream(request):
            chunks.append(chunk)
        assert len(chunks) == 3
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"
