import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, Optional, cast

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    StreamingChunkDTO,
)
from app.core.ai_exceptions import ProviderNotFoundException
from app.core.ai_logging import log_flow_event
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger("ai_service")


def _num(value: Any) -> int | float:
    return value if isinstance(value, (int, float)) else 0


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


class _InstrumentedProvider(BaseLLMProvider):
    """Wraps a provider to emit structured llm.call / llm.error flow events.

    Every LLM request (chat, structured_output, tool_call, embeddings, stream)
    is logged with request_id (from the request context), provider, model,
    latency, and token usage — one choke point for all providers.
    """

    def __init__(self, provider: BaseLLMProvider, provider_name: str):
        self._provider = provider
        self._provider_name = provider_name

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    async def chat(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        return await self._instrument("chat", request, timeout=timeout)

    async def stream(self, request: ChatRequest, timeout: float | None = None) -> Any:
        start = time.perf_counter()
        try:
            chunks = cast(
                "AsyncGenerator[StreamingChunkDTO, None]",
                self._provider.stream(request, timeout=timeout),
            )
            async for chunk in chunks:
                yield chunk
            log_flow_event(
                "llm.stream.complete",
                provider=self._provider_name,
                model=_str(request.model),
                method="stream",
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
                success=True,
            )
        except Exception as exc:
            log_flow_event(
                "llm.error",
                provider=self._provider_name,
                model=_str(request.model),
                method="stream",
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
                error=str(exc)[:300],
                success=False,
            )
            raise

    async def embeddings(self, request: EmbeddingRequest, timeout: float | None = None) -> EmbeddingResponse:
        return await self._instrument("embeddings", request, timeout=timeout)

    async def health_check(self) -> HealthDTO:
        return await self._provider.health_check()

    async def list_models(self) -> list[str]:
        return await self._provider.list_models()

    async def structured_output(
        self, request: ChatRequest, response_schema: Any, timeout: float | None = None
    ) -> ChatResponse:
        return await self._instrument("structured_output", request, timeout=timeout, response_schema=response_schema)

    async def tool_call(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        return await self._instrument("tool_call", request, timeout=timeout)

    async def _instrument(
        self,
        method: str,
        request: ChatRequest | EmbeddingRequest,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        start = time.perf_counter()
        try:
            result = await getattr(self._provider, method)(request, timeout=timeout, **kwargs)
            usage = getattr(result, "usage", None)
            log_flow_event(
                "llm.call",
                provider=self._provider_name,
                model=_str(getattr(result, "model", None)),
                method=method,
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
                prompt_tokens=_num(getattr(usage, "prompt_tokens", 0)),
                completion_tokens=_num(getattr(usage, "completion_tokens", 0)),
                total_tokens=_num(getattr(usage, "total_tokens", 0)),
                success=True,
            )
            return result
        except Exception as exc:
            log_flow_event(
                "llm.error",
                provider=self._provider_name,
                model=_str(getattr(request, "model", None)),
                method=method,
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
                error=str(exc)[:300],
                success=False,
            )
            raise


class LLMProviderFactory:
    """Singleton provider factory with lazy provider loading and instance caching."""

    _instance: Optional["LLMProviderFactory"] = None
    _cache: dict[str, BaseLLMProvider] = {}

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def get_provider(self, provider_name: str) -> BaseLLMProvider:
        provider_key = provider_name.strip().lower()
        if provider_key in self._cache:
            return self._cache[provider_key]

        logger.info("Instantiating provider: %s", provider_key)

        if provider_key == "openai":
            from app.infrastructure.providers.openai_provider import OpenAIProvider

            provider_instance: BaseLLMProvider = OpenAIProvider()
        elif provider_key == "gemini":
            from app.infrastructure.providers.gemini_provider import GeminiProvider

            provider_instance = GeminiProvider()
        elif provider_key == "claude":
            from app.infrastructure.providers.claude_provider import ClaudeProvider

            provider_instance = ClaudeProvider()
        elif provider_key == "azure":
            from app.infrastructure.providers.azure_provider import AzureOpenAIProvider

            provider_instance = AzureOpenAIProvider()
        elif provider_key == "ollama":
            from app.infrastructure.providers.ollama_provider import OllamaProvider

            provider_instance = OllamaProvider()
        elif provider_key == "openrouter":
            from app.infrastructure.providers.openrouter_provider import OpenRouterProvider

            provider_instance = OpenRouterProvider()
        elif provider_key == "deepseek":
            from app.infrastructure.providers.deepseek_provider import DeepSeekProvider

            provider_instance = DeepSeekProvider()
        elif provider_key == "mistral":
            from app.infrastructure.providers.mistral_provider import MistralProvider

            provider_instance = MistralProvider()
        elif provider_key == "bedrock":
            from app.infrastructure.providers.bedrock_provider import BedrockProvider

            provider_instance = BedrockProvider()
        elif provider_key == "mock":
            from app.infrastructure.providers.mock_provider import MockProvider

            provider_instance = MockProvider()
        else:
            raise ProviderNotFoundException(provider_name)

        instrumented = _InstrumentedProvider(provider_instance, provider_key)
        self._cache[provider_key] = instrumented
        return instrumented

    @classmethod
    def clear_cache(cls) -> None:
        if cls._instance:
            cls._instance._cache.clear()
