"""Widget routing-state persistence tests.

The chat handler persists the executed intent as routing state so the next
turn's IntentResolver can continue the active flow deterministically.
"""

from unittest.mock import AsyncMock

from app.api.widget.router import _persist_chat_context
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO


def _chat_response(intent: str) -> ChatResponse:
    return ChatResponse(
        id="resp-1",
        message=MessageDTO(role="assistant", content="Here are some products."),
        metadata={
            "intent": intent,
            "sub_agent": "recommendation",
            "result": {
                "products": [
                    {"product_id": "p1", "title": "Wireless Mouse", "price": "49.99"}
                ]
            },
        },
        model="openai/gpt-4o-mini",
        provider="openrouter",
        usage=UsageDTO(),
        latency_ms=10.0,
    )


async def test_persists_routing_state_from_intent():
    conv = AsyncMock()
    await _persist_chat_context(
        conv,
        "convo-1",
        "store-1",
        "black",
        _chat_response("sales"),
        previous_routing={"active_intent": "recommendation"},
    )
    args = conv.update_conversation_context.await_args.args
    assert args[2] == "store-1"
    routing = args[1]["routing"]
    assert routing["active_intent"] == "sales"
    assert routing["previous_intent"] == "recommendation"


async def test_persists_last_recommendation_and_routing_together():
    conv = AsyncMock()
    await _persist_chat_context(
        conv,
        "convo-1",
        "store-1",
        "black",
        _chat_response("recommendation"),
    )
    context = conv.update_conversation_context.await_args.args[1]
    assert context["routing"]["active_intent"] == "recommendation"
    assert context["last_recommendation"]["query"] == "black"


async def test_no_routing_persisted_without_intent():
    conv = AsyncMock()
    response = _chat_response("recommendation")
    response.metadata.pop("intent")
    response.metadata["result"] = {}
    await _persist_chat_context(conv, "convo-1", "store-1", "hello", response)
    assert conv.update_conversation_context.await_args is None
