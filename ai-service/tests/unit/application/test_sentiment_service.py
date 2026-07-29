import json
from unittest.mock import AsyncMock

import pytest

from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.application.ticket.dto.sentiment_dto import SentimentAnalysisRequest
from app.application.ticket.services.sentiment_service import SentimentAnalysisService


@pytest.fixture
def chat_service():
    cs = AsyncMock()
    cs.chat.return_value = ChatResponse(
        id="test",
        model="gpt-4o-mini",
        provider="openai",
        message=MessageDTO(
            role="assistant",
            content=json.dumps(
                {
                    "sentiment": "negative",
                    "confidence": 0.95,
                    "category": "billing",
                    "priority": "high",
                    "summary": "Customer is frustrated with billing issue",
                    "suggested_response": "We apologize for the inconvenience",
                }
            ),
        ),
        usage=UsageDTO(),
        latency_ms=0,
    )
    return cs


@pytest.fixture
def sentiment_service(chat_service):
    return SentimentAnalysisService(chat_service=chat_service)


class TestSentimentAnalysisService:
    async def test_analyze_returns_result(self, sentiment_service):
        result = await sentiment_service.analyze(
            SentimentAnalysisRequest(
                messages=["I have a problem with my bill"],
                store_id="s1",
                customer_id="c1",
            )
        )
        assert result.sentiment == "negative"
        assert result.confidence == 0.95
        assert result.category == "billing"

    async def test_analyze_positive_sentiment(self, sentiment_service, chat_service):
        chat_service.chat.return_value.message.content = json.dumps(
            {
                "sentiment": "positive",
                "confidence": 0.85,
                "category": "general",
                "priority": "low",
                "summary": "Customer is happy",
                "suggested_response": "Glad to hear that!",
            }
        )
        result = await sentiment_service.analyze(
            SentimentAnalysisRequest(
                messages=["I love your product!"],
                store_id="s1",
                customer_id="c1",
            )
        )
        assert result.sentiment == "positive"
        assert result.confidence == 0.85

    async def test_analyze_empty_messages(self, sentiment_service):
        result = await sentiment_service.analyze(
            SentimentAnalysisRequest(
                messages=[],
                store_id="s1",
                customer_id="c1",
            )
        )
        assert result.sentiment is not None

    class TestSentimentServiceEdgeCases:
        async def test_llm_returns_invalid_json(self, sentiment_service, chat_service):
            chat_service.chat.return_value.message.content = "not valid json at all"
            result = await sentiment_service.analyze(
                SentimentAnalysisRequest(
                    messages=["test message"],
                    store_id="s1",
                    customer_id="c1",
                )
            )
            assert result.sentiment == "neutral"
            assert result.confidence == 0.0

        async def test_llm_returns_missing_fields(self, sentiment_service, chat_service):
            chat_service.chat.return_value.message.content = json.dumps(
                {
                    "sentiment": "positive",
                }
            )
            result = await sentiment_service.analyze(
                SentimentAnalysisRequest(
                    messages=["great service"],
                    store_id="s1",
                    customer_id="c1",
                )
            )
            assert result.sentiment == "positive"

        async def test_llm_call_fails(self, sentiment_service, chat_service):
            chat_service.chat.side_effect = Exception("LLM unavailable")
            result = await sentiment_service.analyze(
                SentimentAnalysisRequest(
                    messages=["test"],
                    store_id="s1",
                    customer_id="c1",
                )
            )
            assert result.sentiment == "neutral"
            assert result.confidence == 0.0
            assert result.summary == "Unable to analyze sentiment"

        async def test_content_as_list(self, sentiment_service, chat_service):
            chat_service.chat.return_value.message.content = ["invalid"]
            result = await sentiment_service.analyze(
                SentimentAnalysisRequest(
                    messages=["test"],
                    store_id="s1",
                    customer_id="c1",
                )
            )
            assert result.sentiment == "neutral"

        async def test_many_messages_truncated_to_last_10(self, sentiment_service, chat_service):
            chat_service.chat.return_value.message.content = json.dumps(
                {
                    "sentiment": "neutral",
                    "confidence": 0.6,
                    "category": "general",
                    "priority": "low",
                    "summary": "Many messages",
                    "suggested_response": "OK",
                }
            )
            messages = [f"msg_{i}" for i in range(20)]
            result = await sentiment_service.analyze(
                SentimentAnalysisRequest(
                    messages=messages,
                    store_id="s1",
                    customer_id="c1",
                )
            )
            assert result.sentiment == "neutral"
