import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.api.ai.dependencies import get_ai_service
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO, EmbeddingResponse

@pytest.fixture
def mock_ai_service():
    service = MagicMock()
    service.chat = AsyncMock()
    service.embeddings = AsyncMock()
    service.structured_output = AsyncMock()
    return service

def test_chat_endpoint(mock_ai_service):
    # Setup mock response
    mock_response = ChatResponse(
        id="resp-id-123",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(role="assistant", content="Hello back!"),
        usage=UsageDTO(prompt_tokens=5, completion_tokens=5, total_tokens=10, cost=0.0001),
        latency_ms=15.0
    )
    mock_ai_service.chat.return_value = mock_response
    
    # Override dependency
    app.dependency_overrides[get_ai_service] = lambda: mock_ai_service
    
    client = TestClient(app)
    payload = {
        "messages": [{"role": "user", "content": "Hello"}],
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "json_mode": False
    }
    
    response = client.post("/api/v1/ai/chat", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["id"] == "resp-id-123"
    assert json_data["message"]["content"] == "Hello back!"
    assert json_data["provider"] == "openai"
    
    # Verify mock was called
    mock_ai_service.chat.assert_called_once()
    
    # Clear override
    app.dependency_overrides.clear()


def test_embeddings_endpoint(mock_ai_service):
    mock_response = EmbeddingResponse(
        model="text-embedding-3-small",
        provider="openai",
        embeddings=[[0.1, 0.2, 0.3]],
        usage=UsageDTO(prompt_tokens=4, completion_tokens=0, total_tokens=4, cost=0.0)
    )
    mock_ai_service.embeddings.return_value = mock_response
    
    app.dependency_overrides[get_ai_service] = lambda: mock_ai_service
    
    client = TestClient(app)
    payload = {
        "input": "Embed this string",
        "model": "text-embedding-3-small"
    }
    
    response = client.post("/api/v1/ai/embeddings", json=payload)
    
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["provider"] == "openai"
    assert json_data["embeddings"] == [[0.1, 0.2, 0.3]]
    
    mock_ai_service.embeddings.assert_called_once()
    app.dependency_overrides.clear()


def test_list_models_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/ai/models")
    
    assert response.status_code == 200
    models_list = response.json()
    assert len(models_list) > 0
    # Check if a known model is present in the list
    gpt_4o_present = any(m["name"] == "gpt-4o" for m in models_list)
    assert gpt_4o_present


def test_list_providers_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/ai/providers")
    
    assert response.status_code == 200
    providers_list = response.json()
    assert len(providers_list) > 0
    # Check if openai provider is listed
    openai_present = any(p["provider"] == "openai" for p in providers_list)
    assert openai_present
