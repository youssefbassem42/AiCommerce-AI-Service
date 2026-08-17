"""SBG gateway provider tests: payload mapping, response parsing,
registry wiring, and streaming-only guardrails (chat/embeddings/structured
output/tool calls raise NotImplementedError).
"""

import json

import pytest

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.infrastructure.providers.bedrock_provider import (
    DEFAULT_BASE_URL,
    BedrockProvider,
    _build_body,
    _parse_response,
)


def test_default_base_url_points_to_sbg_gateway():
    assert DEFAULT_BASE_URL == "http://apiaccess.iti.net.eg/api/v1"


def test_build_body_splits_system_prompts_and_flattens_content():
    body = _build_body(
        ChatRequest(
            model="us.meta.llama3-3-70b-instruct-v1:0",
            messages=[
                MessageDTO(role="system", content="You are a store assistant."),
                MessageDTO(role="system", content="Answer in Arabic."),
                MessageDTO(
                    role="user",
                    content=[{"type": "text", "text": "Describe"}, {"type": "image_url", "image_url": {"url": "x"}}],
                ),
                MessageDTO(role="assistant", content="Hi there"),
            ],
        )
    )
    assert body["model_id"] == "us.meta.llama3-3-70b-instruct-v1:0"
    assert body["system_prompt"] == "You are a store assistant.\n\nAnswer in Arabic."
    assert body["messages"] == [
        {"role": "user", "content": "Describe [Image URL: x]"},
        {"role": "assistant", "content": "Hi there"},
    ]


def test_build_body_omits_empty_parts():
    body = _build_body(
        ChatRequest(
            model="deepseek.v3.2",
            messages=[MessageDTO(role="system", content="  "), MessageDTO(role="user", content="hello")],
        )
    )
    assert "system_prompt" not in body
    assert body["messages"] == [{"role": "user", "content": "hello"}]


def test_parse_response_maps_output_and_usage():
    payload = {
        "request_id": "req-123",
        "model_id": "qwen.qwen3-vl-235b-a22b",
        "output_text": "OK",
        "usage": {
            "input_tokens": 24,
            "output_tokens": 2,
            "total_tokens": 26,
            "stop_reason": "end_turn",
        },
        "actual_cost_usd": "0.000018",
    }
    chunk = _parse_response(payload, "fallback-id", "qwen.qwen3-vl-235b-a22b")
    assert chunk.id == "req-123"
    assert chunk.content == "OK"
    assert chunk.finish_reason == "end_turn"
    assert chunk.usage.prompt_tokens == 24
    assert chunk.usage.completion_tokens == 2
    assert chunk.usage.total_tokens == 26
    assert chunk.usage.cost == 0.000018


@pytest.mark.asyncio
async def test_streaming_only_provider_raises_for_chat_and_embeddings():
    provider = BedrockProvider(api_key="test-key")
    with pytest.raises(NotImplementedError):
        await provider.chat(ChatRequest(model="deepseek.v3.2", messages=[MessageDTO(role="user", content="hi")]))
    with pytest.raises(NotImplementedError):
        await provider.embeddings(type("R", (), {"texts": ["x"]})())  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await provider.structured_output(
            ChatRequest(model="deepseek.v3.2", messages=[MessageDTO(role="user", content="hi")]), {}
        )
    with pytest.raises(NotImplementedError):
        await provider.tool_call(ChatRequest(model="deepseek.v3.2", messages=[MessageDTO(role="user", content="hi")]))


@pytest.mark.asyncio
async def test_stream_yields_text_then_final_chunk_with_usage():
    import httpx

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/student/chat")
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model_id"] == "deepseek.v3.2"
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        return httpx.Response(
            200,
            json={
                "request_id": "req-1",
                "model_id": "deepseek.v3.2",
                "output_text": "Hello!",
                "usage": {"input_tokens": 10, "output_tokens": 3, "total_tokens": 13, "stop_reason": "end_turn"},
                "actual_cost_usd": "0.000010",
            },
        )

    provider = BedrockProvider(api_key="test-key")
    provider.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"Authorization": "Bearer test-key"},
    )
    request = ChatRequest(model="deepseek.v3.2", messages=[MessageDTO(role="user", content="hi")])
    chunks = [c async for c in provider.stream(request)]
    assert len(chunks) == 2
    assert chunks[0].content == "Hello!"
    assert chunks[0].finish_reason is None
    assert chunks[1].content == ""
    assert chunks[1].finish_reason == "end_turn"
    assert chunks[1].usage.total_tokens == 13


@pytest.mark.asyncio
async def test_factory_constructs_bedrock_provider(monkeypatch):
    from app.infrastructure.providers.factory import LLMProviderFactory

    monkeypatch.setenv("SBG_API_KEY", "test-key")
    factory = LLMProviderFactory()
    factory.clear_cache()
    provider = factory.get_provider("bedrock")
    assert isinstance(provider._provider, BedrockProvider)


def test_registry_models_belong_to_bedrock_provider():
    from app.core.model_registry import ModelRegistry

    names = {m.name for m in ModelRegistry.list_models_by_provider("bedrock")}
    assert names == {
        "deepseek.v3.2",
        "openai.gpt-oss-safeguard-120b",
        "openai.gpt-oss-safeguard-20b",
        "openai.gpt-oss-120b-1:0",
        "openai.gpt-oss-20b-1:0",
        "qwen.qwen3-vl-235b-a22b",
        "us.meta.llama3-3-70b-instruct-v1:0",
        "mistral.voxtral-small-24b-2507",
    }
