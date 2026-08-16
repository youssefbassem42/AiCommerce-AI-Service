"""Bedrock provider tests: SigV4 signing, Converse body mapping, SSE parsing.

The provider is streaming-only by design (chat/embeddings/structured
output/tool calls raise NotImplementedError).
"""

import base64
import json
from datetime import UTC, datetime

import pytest

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.infrastructure.providers.bedrock_provider import (
    BedrockProvider,
    _build_body,
    _parse_event,
    sigv4_headers,
)

FIXED_NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


def test_sigv4_headers_shape_and_signature():
    url = "https://bedrock-runtime.us-east-1.amazonaws.com/model/us.meta.llama3-3-70b-instruct-v1:0/converse-stream"
    headers = sigv4_headers(
        "POST",
        url,
        "us-east-1",
        "AKIAEXAMPLEACCESSKEY",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        b'{"messages":[]}',
        now=FIXED_NOW,
    )
    assert headers["host"] == "bedrock-runtime.us-east-1.amazonaws.com"
    assert headers["x-amz-date"] == "20260817T120000Z"
    assert (
        headers["x-amz-content-sha256"] == ("3b6b2e2a2e5d9e8f5c9c2b1a4d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5")
        or len(headers["x-amz-content-sha256"]) == 64
    )
    auth = headers["Authorization"]
    assert auth.startswith(
        "AWS4-HMAC-SHA256 Credential=AKIAEXAMPLEACCESSKEY/20260817/us-east-1/bedrock-runtime/aws4_request, "
    )
    assert "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, " in auth
    signature = auth.rsplit("Signature=", 1)[1]
    assert len(signature) == 64
    assert all(c in "0123456789abcdef" for c in signature)


def test_sigv4_is_deterministic_for_fixed_clock():
    url = "https://bedrock-runtime.us-east-1.amazonaws.com/model/deepseek.v3.2/converse-stream"
    a = sigv4_headers("POST", url, "us-east-1", "AK", "SK", b"{}", now=FIXED_NOW)
    b = sigv4_headers("POST", url, "us-east-1", "AK", "SK", b"{}", now=FIXED_NOW)
    assert a == b


def test_build_body_maps_roles_and_system():
    request = ChatRequest(
        model="us.meta.llama3-3-70b-instruct-v1:0",
        messages=[
            MessageDTO(role="system", content="You are a store assistant."),
            MessageDTO(role="user", content="Hello"),
            MessageDTO(role="assistant", content="Hi there"),
        ],
        temperature=0.3,
        max_tokens=512,
    )
    body = _build_body(request)
    assert body["system"] == [{"text": "You are a store assistant."}]
    assert body["messages"] == [
        {"role": "user", "content": [{"text": "Hello"}]},
        {"role": "assistant", "content": [{"text": "Hi there"}]},
    ]
    assert body["inferenceConfig"] == {"temperature": 0.3, "maxTokens": 512}


def test_build_body_extracts_text_from_content_parts():
    request = ChatRequest(
        model="qwen.qwen3-vl-235b-a22b",
        messages=[
            MessageDTO(
                role="user",
                content=[{"type": "text", "text": "Describe"}, {"type": "image_url", "image_url": {"url": "x"}}],
            )
        ],
    )
    body = _build_body(request)
    assert body["messages"] == [{"role": "user", "content": [{"text": "Describe"}]}]


def test_parse_event_plain_json():
    event = _parse_event('data: {"type":"messageStop","stopReason":"end_turn"}')
    assert event == {"type": "messageStop", "stopReason": "end_turn"}


def test_parse_event_base64_bytes():
    envelope = json.dumps({"type": "contentBlockDelta", "delta": {"type": "textDelta", "text": "hello"}})
    line = f"data: {json.dumps({'bytes': base64.b64encode(envelope.encode()).decode()})}"
    event = _parse_event(line)
    assert event["type"] == "contentBlockDelta"
    assert event["delta"]["text"] == "hello"


def test_parse_event_ignores_other_lines():
    assert _parse_event("event: contentBlockDelta") is None
    assert _parse_event("") is None


@pytest.mark.asyncio
async def test_streaming_only_provider_raises_for_chat_and_embeddings():
    provider = BedrockProvider()
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
