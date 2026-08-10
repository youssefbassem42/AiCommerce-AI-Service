"""Phase B correlation tests (B-01..B-05)."""

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from httpx import ASGITransport, AsyncClient

from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.application.services.chat_service import ChatService
from app.application.widget.token_service import WidgetTokenService
from app.core.request_context import set_request_id
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.middleware.request_context import HEADER_LEGACY, HEADER_PRIMARY, RequestContextMiddleware


def _correlation_app() -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    async def probe():
        return JSONResponse({})

    @app.post("/stream")
    async def stream():
        async def events():
            yield b"data: hello\n\n"

        return StreamingResponse(events())

    app.add_middleware(RequestContextMiddleware)
    return app


@pytest.mark.asyncio
async def test_b01_incoming_request_id_is_echoed():
    async with AsyncClient(transport=ASGITransport(app=_correlation_app()), base_url="http://test") as client:
        response = await client.get("/probe", headers={HEADER_PRIMARY: "test-123"})
        assert response.status_code == 200
        assert response.headers[HEADER_PRIMARY] == "test-123"
        assert response.headers[HEADER_LEGACY] == "test-123"


@pytest.mark.asyncio
async def test_b02_missing_header_generates_uuid_and_echoes():
    async with AsyncClient(transport=ASGITransport(app=_correlation_app()), base_url="http://test") as client:
        response = await client.get("/probe")
        assert response.status_code == 200
        request_id = response.headers[HEADER_PRIMARY]
        uuid.UUID(request_id)  # raises if not a valid UUID
        assert response.headers[HEADER_LEGACY] == request_id


@pytest.mark.asyncio
async def test_b02_legacy_x_correlation_id_accepted_as_alias():
    async with AsyncClient(transport=ASGITransport(app=_correlation_app()), base_url="http://test") as client:
        response = await client.get("/probe", headers={HEADER_LEGACY: "legacy-456"})
        assert response.headers[HEADER_PRIMARY] == "legacy-456"


@pytest.mark.asyncio
async def test_b03_chat_metrics_use_request_id(caplog):
    mock_factory = MagicMock()
    mock_provider = AsyncMock()
    mock_provider.chat.return_value = ChatResponse(
        id="resp-1",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(role="assistant", content="hi"),
        usage=UsageDTO(prompt_tokens=5, completion_tokens=5, total_tokens=10, cost=0.001),
        latency_ms=1.0,
    )
    mock_factory.get_provider.return_value = mock_provider
    service = ChatService(provider_factory=mock_factory)

    set_request_id("req-abc-123")
    try:
        with caplog.at_level(logging.INFO, logger="ai_service"):
            await service.chat(ChatRequest(messages=[MessageDTO(role="user", content="Hello")], model="gpt-4o-mini"))
    finally:
        set_request_id("")

    assert any("req-abc-123" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_b04_widget_tenant_context_carries_request_id():
    from app.api.widget.dependencies import get_widget_tenant_context

    request = MagicMock()
    request.state.actor_type = "widget"
    request.state.store_id = "store-1"
    request.state.organization_id = "org-1"
    request.state.widget_id = "wid_1"
    request.state.request_id = "req-widget-1"

    context = get_widget_tenant_context(request)
    assert isinstance(context, TenantContext)
    assert context.request_id == "req-widget-1"
    assert context.store_id == "store-1"
    assert context.actor_type == "widget"


@pytest.mark.asyncio
async def test_b05_streaming_response_carries_request_id():
    async with (
        AsyncClient(transport=ASGITransport(app=_correlation_app()), base_url="http://test") as client,
        client.stream("POST", "/stream") as response,
    ):
        assert response.headers[HEADER_PRIMARY] == response.headers[HEADER_PRIMARY]
        content = [chunk async for chunk in response.aiter_bytes()]
        assert b"hello" in b"".join(content)


@pytest.mark.asyncio
async def test_b06_widget_token_roundtrip_unchanged():
    """Phase B must not alter the widget token contract."""
    service = WidgetTokenService()
    token, expires_in = service.create_session_token("wid_x", "store-1", "org-1", ["rag:chat"])
    claims = service.validate(token)
    assert claims.widget_id == "wid_x"
    assert expires_in == 900
