"""Widget bedrock streaming path: streaming-only models (Bedrock/SBG gateway)
are answered by aggregating provider.stream() chunks inside the conversation
workflow's general-answer node, while product intents keep using sub-agents.
"""

import pytest

from app.agents.coordinator.nodes import chat_via_streaming_provider, is_streaming_only_provider
from app.application.dto.ai_dto import StreamingChunkDTO, UsageDTO


def test_is_streaming_only_provider_matches_bedrock_models():
    assert is_streaming_only_provider("deepseek.v3.2") is True
    assert is_streaming_only_provider("qwen.qwen3-vl-235b-a22b") is True
    assert is_streaming_only_provider("us.meta.llama3-3-70b-instruct-v1:0") is True


def test_is_streaming_only_provider_false_for_other_models_and_unknown():
    assert is_streaming_only_provider("gpt-4o-mini") is False
    assert is_streaming_only_provider("does-not-exist") is False


@pytest.mark.asyncio
async def test_chat_via_streaming_provider_aggregates_chunks(monkeypatch):
    async def fake_stream(self, request):
        assert request.model == "deepseek.v3.2"
        assert request.messages[0].role == "system"
        assert "Store information for reference" in request.messages[0].content
        assert request.messages[-1].content == "hello"
        assert request.max_tokens == 200
        yield StreamingChunkDTO(id="c1", model="deepseek.v3.2", provider="bedrock", content="Hello ")
        yield StreamingChunkDTO(id="c1", model="deepseek.v3.2", provider="bedrock", content="there")
        yield StreamingChunkDTO(
            id="c1",
            model="deepseek.v3.2",
            provider="bedrock",
            content="",
            finish_reason="end_turn",
            usage=UsageDTO(prompt_tokens=10, completion_tokens=3, total_tokens=13, cost=0.00001),
        )

    fake_provider = type("FakeProvider", (), {"stream": fake_stream})()
    monkeypatch.setattr(
        "app.agents.coordinator.nodes.LLMProviderFactory",
        lambda: type("F", (), {"get_provider": lambda self, p: fake_provider})(),
    )

    response = await chat_via_streaming_provider(
        model="deepseek.v3.2",
        messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hey"}],
        user_input="hello",
        context={"knowledge_context": [{"content": "store facts", "document_title": "Policies"}]},
        temperature=0.3,
        max_tokens=200,
    )
    assert response.provider == "bedrock"
    assert response.message.content == "Hello there"
    assert response.usage.total_tokens == 13
    assert response.metadata == {"finish_reason": "end_turn"}
