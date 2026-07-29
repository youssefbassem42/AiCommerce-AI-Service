from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.ai.dependencies import get_ai_service
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.main import app


def test_chat_endpoint():
    mock_service = MagicMock()
    mock_response = ChatResponse(
        id="test-id",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(role="assistant", content="Mock response: hello"),
        usage=UsageDTO(prompt_tokens=2, completion_tokens=5, total_tokens=7, cost=0.0),
        latency_ms=5.0,
    )
    mock_service.chat = AsyncMock(return_value=mock_response)

    app.dependency_overrides[get_ai_service] = lambda: mock_service
    client = TestClient(app)

    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 200
        assert response.json() == {"response": "Mock response: hello"}
    finally:
        app.dependency_overrides.clear()
