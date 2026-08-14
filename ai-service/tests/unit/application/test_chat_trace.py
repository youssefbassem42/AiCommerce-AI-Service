"""Phase 0 exit criterion (workflow hop): a single message_id is carried from
metadata through store -> conversation -> intent -> agent result -> response."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.recommendation.dto.recommendation_dto import RecommendationResponse
from app.application.services.orchestration_service import OrchestrationService
from app.core.request_context import set_request_id
from app.infrastructure.providers.factory import LLMProviderFactory


@pytest.fixture
def llm():
    provider = AsyncMock()

    def structured_side_effect(request, response_schema):
        prompt = request.messages[-1].content
        if "classify" in prompt.lower():
            content = '{"intent": "recommendation", "confidence": 0.9}'
        else:
            content = '{"key_topics": [], "customer_preferences": [], "store_facts": [], "sentiment": "neutral"}'
        response = MagicMock()
        response.message.content = content
        return response

    provider.structured_output.side_effect = structured_side_effect

    def chat_side_effect(request):
        response = MagicMock()
        response.message.content = "Fallback answer."
        return response

    provider.chat.side_effect = chat_side_effect
    return provider


@pytest.fixture
def recommendation_service():
    service = AsyncMock()
    service.recommend.return_value = RecommendationResponse(
        query="recommend a phone",
        store_id="store_1",
        customer_id="customer_1",
        rationale="Top pick: Phone X.",
    )
    return service


def _flow_events(caplog):
    events = []
    for record in caplog.records:
        if record.name == "ai.flow":
            events.append(json.loads(record.getMessage()))
    return events


class TestChatTurnTrace:
    @pytest.mark.asyncio
    async def test_message_id_traces_intent_and_agent_result(self, llm, recommendation_service, caplog):
        set_request_id("req-trace-1")
        service = OrchestrationService(
            provider_factory=LLMProviderFactory(),
            conversation_service=AsyncMock(),
            memory_repo=AsyncMock(),
            recommendation_service=recommendation_service,
            bundle_service=AsyncMock(),
            llm=llm,
        )

        with caplog.at_level(logging.INFO, logger="ai.flow"):
            response = await service.chat(
                user_input="recommend a phone",
                store_id="store_1",
                customer_id="customer_1",
                conversation_id="convo_1",
                metadata={"message_id": "msg-trace-1"},
            )
        set_request_id("")

        assert response.metadata["message_id"] == "msg-trace-1"
        assert response.metadata["request_id"] == "req-trace-1"
        assert response.metadata["intent"] == "recommendation"

        events = _flow_events(caplog)
        intent_events = [e for e in events if e["event"] == "intent.classified"]
        result_events = [e for e in events if e["event"] == "agent.result"]

        assert len(intent_events) == 1
        assert intent_events[0]["message_id"] == "msg-trace-1"
        assert intent_events[0]["intent"] == "recommendation"
        assert intent_events[0]["request_id"] == "req-trace-1"
        assert intent_events[0]["store_id"] == "store_1"

        assert len(result_events) == 1
        assert result_events[0]["message_id"] == "msg-trace-1"
        assert result_events[0]["sub_agent"] == "recommendation"
        assert result_events[0]["conversation_id"] == "convo_1"

        recommendation_service.recommend.assert_awaited_once()
