"""SBG gateway provider — Bedrock-hosted models, single-shot JSON responses.

Accesses Bedrock-hosted models through the ITI SBG gateway (an
OpenAI-style portal exposing Bedrock model IDs). The gateway does NOT
support SSE streaming — it returns a single JSON response per request —
so ``stream()`` makes one request and yields the full text as one chunk
(the widget renders chunks identically). ``structured_output()`` makes
the same single request with the canonical JSON schema injected into the
user prompt.

Config (env):
    SBG_API_KEY        (required, via KeyManager)
    SBG_API_BASE_URL   (default http://apiaccess.iti.net.eg/api/v1)

POST {base_url}/student/chat
    Authorization: Bearer <SBG_API_KEY>
    Body: {"model_id", "messages": [{"role","content"}], "system_prompt"}
    Response: {"request_id", "model_id", "output_text", "usage": {...},
               "estimated_cost_usd", "actual_cost_usd", "status"}
"""

import logging
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    MessageDTO,
    StreamingChunkDTO,
    UsageDTO,
)
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.schema_utils import schema_description
from app.infrastructure.security.key_manager import KeyManager
from app.utils.ai_error_handler import map_provider_exception

logger = logging.getLogger("ai_service")

DEFAULT_BASE_URL = "http://apiaccess.iti.net.eg/api/v1"
DEFAULT_TIMEOUT = 120.0
_ENDPOINT = "/student/chat"


def _build_body(request: ChatRequest) -> dict[str, Any]:
    """Map a ChatRequest to the SBG gateway payload (system prompts split out)."""
    system_parts: list[str] = []
    messages: list[dict[str, str]] = []
    for msg in request.messages:
        if msg.role == "system":
            if msg.content:
                system_parts.append(msg.content if isinstance(msg.content, str) else str(msg.content))
            continue
        content = msg.content
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item["text"])
                elif isinstance(item, dict) and item.get("type") == "image_url":
                    text_parts.append(f"[Image URL: {item['image_url']['url']}]")
                else:
                    text_parts.append(str(item))
            content = " ".join(text_parts)
        if not str(content).strip():
            continue
        messages.append({"role": msg.role, "content": str(content)})

    body: dict[str, Any] = {"model_id": request.model, "messages": messages}
    if system_parts:
        joined = "\n\n".join(p for p in system_parts if p.strip())
        if joined:
            body["system_prompt"] = joined
    return body


def _parse_response(payload: dict[str, Any], request_id: str, model: str) -> StreamingChunkDTO:
    """Convert the SBG gateway JSON response into a final streaming chunk."""
    usage_raw = payload.get("usage") or {}
    usage = UsageDTO(
        prompt_tokens=int(usage_raw.get("input_tokens", 0)),
        completion_tokens=int(usage_raw.get("output_tokens", 0)),
        total_tokens=int(usage_raw.get("total_tokens", 0)),
        cost=float(payload.get("actual_cost_usd") or 0.0),
    )
    finish_reason = usage_raw.get("stop_reason") or "stop"
    return StreamingChunkDTO(
        id=payload.get("request_id") or request_id,
        model=payload.get("model_id") or model,
        provider="bedrock",
        content=payload.get("output_text") or "",
        finish_reason=finish_reason,
        usage=usage,
    )


class BedrockProvider(BaseLLMProvider):
    """
    Bedrock models via the SBG gateway — single-shot JSON responses.
    ``stream()`` and ``structured_output()`` are supported; plain
    ``chat()``, embeddings and tool calling are not.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or KeyManager().require_provider_api_key("bedrock", env_var="SBG_API_KEY")
        self.base_url = (base_url or os.getenv("SBG_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT, connect=20.0),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def chat(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        raise NotImplementedError("Bedrock gateway provider supports streaming only")

    async def stream(
        self, request: ChatRequest, timeout: float | None = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        url = f"{self.base_url}{_ENDPOINT}"
        request_id = f"bedrock-{int(time.time() * 1000)}"
        try:
            resp = await self.client.post(url, json=_build_body(request), timeout=timeout or DEFAULT_TIMEOUT)
            if resp.status_code != 200:
                raise RuntimeError(f"SBG gateway error {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
        except Exception as e:
            raise map_provider_exception("bedrock", e)

        chunk = _parse_response(payload, request_id, request.model)
        if chunk.content:
            yield StreamingChunkDTO(
                id=chunk.id,
                model=chunk.model,
                provider="bedrock",
                content=chunk.content,
            )
        yield StreamingChunkDTO(
            id=chunk.id,
            model=chunk.model,
            provider="bedrock",
            content="",
            finish_reason=chunk.finish_reason,
            usage=chunk.usage,
        )

    async def embeddings(self, request: EmbeddingRequest, timeout: float | None = None) -> EmbeddingResponse:
        raise NotImplementedError("Bedrock gateway provider supports streaming only")

    async def health_check(self) -> HealthDTO:
        start_time = time.perf_counter()
        try:
            await self.client.get(self.base_url, timeout=httpx.Timeout(10.0, connect=10.0))
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(status="healthy", provider="bedrock", latency_ms=latency)
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return HealthDTO(
                status="unhealthy",
                provider="bedrock",
                latency_ms=latency,
                details=str(e),
            )

    async def list_models(self) -> list[str]:
        from app.core.model_registry import ModelRegistry

        return [m.name for m in ModelRegistry.list_models_by_provider("bedrock")]

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: float | None = None
    ) -> ChatResponse:
        """
        Generate structured output. The gateway has no native structured
        mode, so the canonical JSON schema is injected into the user prompt
        and the raw ``output_text`` is returned for callers to parse —
        exactly the contract the other prompt-based providers follow.
        """
        start_time = time.perf_counter()
        request_copy = ChatRequest(**request.model_dump())
        request_copy.json_mode = True

        instruction = (
            "\nReturn a JSON object matching this schema (the data itself, "
            "NOT the schema definition):\n"
            f"{schema_description(response_schema)}"
        )
        if request_copy.messages:
            last_msg = request_copy.messages[-1]
            if isinstance(last_msg.content, str):
                last_msg.content += instruction
            else:
                last_msg.content.append({"type": "text", "text": instruction})

        url = f"{self.base_url}{_ENDPOINT}"
        request_id = f"bedrock-{int(time.time() * 1000)}"
        try:
            resp = await self.client.post(url, json=_build_body(request_copy), timeout=timeout or DEFAULT_TIMEOUT)
            if resp.status_code != 200:
                raise RuntimeError(f"SBG gateway error {resp.status_code}: {resp.text[:300]}")
            payload = resp.json()
        except Exception as e:
            raise map_provider_exception("bedrock", e)

        chunk = _parse_response(payload, request_id, request.model)
        return ChatResponse(
            id=chunk.id,
            model=chunk.model,
            provider="bedrock",
            message=MessageDTO(role="assistant", content=chunk.content),
            usage=chunk.usage,
            latency_ms=(time.perf_counter() - start_time) * 1000,
        )

    async def tool_call(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        raise NotImplementedError("Bedrock gateway provider supports streaming only")
