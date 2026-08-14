"""Phase 0: LLMProviderFactory instrumentation logs structured llm.call/llm.error events."""

import json
import logging

import pytest

from app.core.request_context import set_request_id
from app.infrastructure.providers.factory import LLMProviderFactory


@pytest.fixture(autouse=True)
def clear_factory_cache():
    LLMProviderFactory.clear_cache()
    yield
    LLMProviderFactory.clear_cache()


def _flow_events(caplog):
    events = []
    for record in caplog.records:
        if record.name == "ai.flow":
            events.append(json.loads(record.getMessage()))
    return events


class TestProviderInstrumentation:
    @pytest.mark.asyncio
    async def test_chat_logs_llm_call_with_request_id(self, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            set_request_id("req-1")
            provider = LLMProviderFactory().get_provider("mock")
            from app.application.dto.ai_dto import ChatRequest, MessageDTO

            response = await provider.chat(
                ChatRequest(
                    messages=[MessageDTO(role="user", content="hello")],
                    model="mock-model",
                )
            )
            set_request_id("")

        assert response.message.content.startswith("Mock response")
        events = _flow_events(caplog)
        call_events = [e for e in events if e["event"] == "llm.call"]
        assert len(call_events) == 1
        call = call_events[0]
        assert call["request_id"] == "req-1"
        assert call["provider"] == "mock"
        assert call["method"] == "chat"
        assert call["success"] is True

    @pytest.mark.asyncio
    async def test_failure_logs_llm_error(self, caplog):
        with caplog.at_level(logging.INFO, logger="ai.flow"):
            set_request_id("req-2")
            provider = LLMProviderFactory().get_provider("mock")
            from unittest.mock import patch

            from app.application.dto.ai_dto import ChatRequest, MessageDTO

            with (
                patch.object(provider._provider, "chat", side_effect=RuntimeError("boom")),
                pytest.raises(RuntimeError),
            ):
                await provider.chat(ChatRequest(messages=[MessageDTO(role="user", content="hello")], model="m"))
            set_request_id("")

        events = _flow_events(caplog)
        error_events = [e for e in events if e["event"] == "llm.error"]
        assert len(error_events) == 1
        assert error_events[0]["request_id"] == "req-2"
        assert error_events[0]["error"] == "boom"
        assert error_events[0]["success"] is False

    @pytest.mark.asyncio
    async def test_factory_returns_same_instrumented_instance(self):
        first = LLMProviderFactory().get_provider("mock")
        second = LLMProviderFactory().get_provider("mock")
        assert first is second
        assert hasattr(first, "_provider")
