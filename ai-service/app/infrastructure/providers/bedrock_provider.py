"""Amazon Bedrock provider — streaming chat ONLY (converse-stream HTTP API).

Credentials come from the standard AWS env vars (``AWS_ACCESS_KEY_ID``,
``AWS_SECRET_ACCESS_KEY``, ``AWS_REGION``, default region ``us-east-1``).
Requests are signed with AWS Signature Version 4 and sent with httpx
(no boto3 dependency). Embeddings are not supported by this provider.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import httpx

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    StreamingChunkDTO,
    UsageDTO,
)
from app.core.ai_exceptions import ProviderCredentialsError
from app.core.ai_settings import ai_settings
from app.infrastructure.providers.base import BaseLLMProvider
from app.utils.token_utils import calculate_cost

logger = logging.getLogger("ai_service")

_SERVICE = "bedrock-runtime"
_DEFAULT_REGION = "us-east-1"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sigv4_headers(
    method: str,
    url: str,
    region: str,
    access_key: str,
    secret_key: str,
    payload: bytes,
    now: datetime | None = None,
) -> dict[str, str]:
    """Build AWS Signature Version 4 request headers for the given payload."""
    now = now or datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = _sha256_hex(payload)
    host = url.split("://", 1)[1].split("/", 1)[0]
    path = url.split("://", 1)[1].split("?", 1)[0]

    canonical_headers = (
        f"content-type:application/json\nhost:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([method.upper(), path, "", canonical_headers, signed_headers, payload_hash])
    scope = f"{date_stamp}/{region}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, _sha256_hex(canonical_request.encode("utf-8"))])
    k_date = _hmac(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac(k_date, region)
    k_service = _hmac(k_region, _SERVICE)
    k_signing = _hmac(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
        ),
        "content-type": "application/json",
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }


def _message_text(message: Any) -> str:
    """Flatten a message's content to plain text (text parts only)."""
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        parts = []
        for item in message.content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return " ".join(parts)
    return str(message.content)


def _build_body(request: ChatRequest) -> dict[str, Any]:
    """Map a ChatRequest to the Bedrock Converse API body (text only)."""
    system: list[str] = []
    messages: list[dict[str, Any]] = []
    for msg in request.messages:
        if msg.role == "system":
            system.append(_message_text(msg))
            continue
        text = _message_text(msg)
        if not text.strip():
            continue
        role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": role, "content": [{"text": text}]})

    body: dict[str, Any] = {"messages": messages}
    if system:
        body["system"] = [{"text": t} for t in system if t.strip()]
    inference_config: dict[str, Any] = {}
    if request.max_tokens is not None:
        inference_config["maxTokens"] = request.max_tokens
    if request.temperature is not None:
        inference_config["temperature"] = request.temperature
    if request.top_p is not None:
        inference_config["topP"] = request.top_p
    if inference_config:
        body["inferenceConfig"] = inference_config
    return body


def _parse_event(line: str) -> dict[str, Any] | None:
    """Parse one SSE line of the converse-stream response."""
    line = line.strip()
    if not line.startswith("data:"):
        return None
    try:
        payload = json.loads(line[5:].strip())
    except (ValueError, TypeError):
        return None
    if isinstance(payload, dict) and "bytes" in payload:
        try:
            payload = json.loads(base64.b64decode(payload["bytes"]))
        except (ValueError, TypeError):
            return None
    return payload if isinstance(payload, dict) else None


class BedrockProvider(BaseLLMProvider):
    """Bedrock chat via ``converse-stream`` — streaming only."""

    def __init__(self):
        self.region = os.getenv("AWS_REGION") or _DEFAULT_REGION

    def _credentials(self) -> tuple[str, str]:
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            raise ProviderCredentialsError(
                "bedrock",
                "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY",
                extra_hint="set the standard AWS env vars (region: AWS_REGION, default us-east-1)",
            )
        return access_key, secret_key

    async def chat(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        raise NotImplementedError("Bedrock provider supports streaming only")

    async def stream(
        self, request: ChatRequest, timeout: float | None = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        access_key, secret_key = self._credentials()
        model = request.model
        url = f"https://{_SERVICE}.{self.region}.amazonaws.com/model/{model}/converse-stream"
        payload = json.dumps(_build_body(request)).encode("utf-8")
        headers = sigv4_headers("POST", url, self.region, access_key, secret_key, payload)
        actual_timeout = timeout or ai_settings.REQUEST_TIMEOUT
        request_id = f"bedrock-{int(time.time() * 1000)}"
        finish_reason: str | None = None
        usage: UsageDTO | None = None

        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(actual_timeout)) as client,
            client.stream("POST", url, content=payload, headers=headers) as resp,
        ):
            if resp.status_code != 200:
                error_body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"Bedrock error {resp.status_code}: {error_body[:300]}")
            async for line in resp.aiter_lines():
                event = _parse_event(line)
                if event is None:
                    continue
                if event.get("type") == "contentBlockDelta":
                    text = event.get("delta", {}).get("text") or ""
                    if text:
                        yield StreamingChunkDTO(
                            id=request_id,
                            model=model,
                            provider="bedrock",
                            content=text,
                        )
                elif event.get("type") == "messageStop":
                    finish_reason = event.get("stopReason") or "stop"
                elif event.get("type") == "metadata":
                    u = event.get("usage") or {}
                    prompt_tokens = u.get("inputTokens", 0)
                    completion_tokens = u.get("outputTokens", 0)
                    usage = UsageDTO(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=u.get("totalTokens", prompt_tokens + completion_tokens),
                        cost=calculate_cost(prompt_tokens, completion_tokens, model),
                    )

        yield StreamingChunkDTO(
            id=request_id,
            model=model,
            provider="bedrock",
            content="",
            finish_reason=finish_reason or "stop",
            usage=usage,
        )

    async def embeddings(self, request: EmbeddingRequest, timeout: float | None = None) -> EmbeddingResponse:
        raise NotImplementedError("Bedrock provider supports streaming only")

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            self._credentials()
            return HealthDTO(
                status="healthy",
                provider="bedrock",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 3),
            )
        except Exception as e:
            return HealthDTO(
                status="unhealthy",
                provider="bedrock",
                latency_ms=round((time.perf_counter() - start_time) * 1000, 3),
                details=str(e),
            )

    async def list_models(self) -> list[str]:
        from app.core.model_registry import ModelRegistry

        return [m.name for m in ModelRegistry.list_models_by_provider("bedrock")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: float | None = None
    ) -> ChatResponse:
        raise NotImplementedError("Bedrock provider supports streaming only")

    async def tool_call(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        raise NotImplementedError("Bedrock provider supports streaming only")
