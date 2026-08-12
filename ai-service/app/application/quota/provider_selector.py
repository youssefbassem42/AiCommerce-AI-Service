"""Plan-driven provider selection and failover (spec §16-20, §41-44).

The consumer never chooses provider or model; the selector derives both from
the plan policy (allowed providers/models from the trusted .NET context) and
fails over across allowed providers on transient/provider-quota failures.
A provider the plan does not allow is never selected.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from app.application.dto.ai_dto import (
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    HealthDTO,
    StreamingChunkDTO,
)
from app.application.quota.run_context import get_quota_run
from app.application.quota.usage_normalizer import UsageNormalizer
from app.core.ai_exceptions import (
    AllProvidersFailedException,
    AuthenticationException,
    ProviderUnavailableException,
    RateLimitException,
    StreamingException,
)
from app.core.ai_settings import ai_settings
from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

# Provider failures that justify switching to another plan-allowed provider.
_FALLOVER_TRIGGERS = (
    ProviderUnavailableException,
    RateLimitException,
    AuthenticationException,
    StreamingException,
    TimeoutError,
)


class ProviderSelector:
    """Resolves providers/models from the plan and executes with failover."""

    def __init__(self, factory: LLMProviderFactory | None = None) -> None:
        self._factory = factory or LLMProviderFactory()

    def provider_order(self, plan: PlanPolicy) -> list[str]:
        """Allowed providers ordered by preference (default provider first)."""
        ordered: list[str] = []
        preferred = [ai_settings.DEFAULT_PROVIDER, *plan.allowed_providers]
        for provider in preferred:
            if provider in plan.allowed_providers and provider not in ordered:
                ordered.append(provider)
        return ordered

    def model_for_provider(self, plan: PlanPolicy, provider: str, requested: str | None = None) -> str:
        """Best plan-allowed model for a provider (client request cannot override).

        Preference: requested model (only if plan-allowed on this provider),
        then the plan fallback model, then the first allowed model of the
        provider.
        """
        for model in plan.allowed_models:
            if self._provider_of(model) == provider and model == (requested or ""):
                return model
        for model in plan.allowed_models:
            if self._provider_of(model) == provider and model == (plan.fallback_model or ""):
                return model
        for model in plan.allowed_models:
            if self._provider_of(model) == provider:
                return model
        return plan.fallback_model or ai_settings.DEFAULT_MODEL

    async def execute_chat(self, request: ChatRequest, plan: PlanPolicy) -> tuple[ChatResponse, str, str]:
        """Execute the request across plan-allowed providers; first success wins.

        Returns ``(response, provider_name, model_used)`` and raises
        ``AllProvidersFailedException`` when every allowed provider fails.
        """
        requested_model = request.model
        last_error: Exception | None = None
        for provider in self.provider_order(plan):
            model = self.model_for_provider(plan, provider, requested_model)
            request.model = model
            try:
                instance = self._factory.get_provider(provider)
                response = await instance.chat(request)
                response.model = model
                response.provider = provider
                return response, provider, model
            except _FALLOVER_TRIGGERS as exc:
                logger.warning(
                    "Provider '%s' failed (transient): %s — trying next plan-allowed provider", provider, exc
                )
                last_error = exc
            except Exception as exc:
                logger.warning(
                    "Provider '%s' failed (unexpected): %s — trying next plan-allowed provider", provider, exc
                )
                last_error = exc

        raise AllProvidersFailedException(details=str(last_error or "all plan-allowed providers failed"))

    async def execute_stream(
        self,
        request: ChatRequest,
        plan: PlanPolicy,
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        """Stream from plan-allowed providers with failover (non-streaming failure only)."""
        requested_model = request.model
        last_error: Exception | None = None
        for provider in self.provider_order(plan):
            model = self.model_for_provider(plan, provider, requested_model)
            request.model = model
            try:
                instance = self._factory.get_provider(provider)
                async for chunk in instance.stream(request):
                    yield chunk
                return
            except _FALLOVER_TRIGGERS as exc:
                logger.warning("Stream provider '%s' failed: %s — trying next", provider, exc)
                last_error = exc
        raise AllProvidersFailedException(details=str(last_error or "all plan-allowed providers failed"))

    @staticmethod
    def _provider_of(model: str) -> str | None:
        from app.core.model_registry import ModelRegistry

        info = ModelRegistry.get_model_info(model)
        return info.provider if info else None


class PlanFailoverProvider(BaseLLMProvider):
    """BaseLLMProvider facade resolving the plan from the active quota run.

    Used as the ``llm`` injected into orchestration workflows/agents so every
    downstream LLM call is executed against plan-allowed providers with
    failover — without redesigning the workflows (spec §41).
    """

    def __init__(self, factory: LLMProviderFactory | None = None) -> None:
        self._factory = factory or LLMProviderFactory()
        self._selector = ProviderSelector(self._factory)

    def _plan(self) -> PlanPolicy | None:
        run = get_quota_run()
        return run.plan if run else None

    async def chat(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        plan = self._plan()
        if plan is None:
            instance = self._factory.get_provider(ai_settings.DEFAULT_PROVIDER)
            return await instance.chat(request, timeout=timeout)
        response, provider, model = await self._selector.execute_chat(request, plan)
        usage = UsageNormalizer.normalize(response)
        run = get_quota_run()
        if run is not None:
            run.record(provider, model, usage)
        return response

    async def stream(
        self, request: ChatRequest, timeout: float | None = None
    ) -> AsyncGenerator[StreamingChunkDTO, None]:
        plan = self._plan()
        if plan is None:
            instance = self._factory.get_provider(ai_settings.DEFAULT_PROVIDER)
            async for chunk in instance.stream(request, timeout=timeout):
                yield chunk
            return
        async for chunk in self._selector.execute_stream(request, plan):
            if chunk.usage is not None:
                run = get_quota_run()
                if run is not None:
                    run.record(chunk.provider or request.model, chunk.model, chunk.usage)
            yield chunk

    async def embeddings(self, request: EmbeddingRequest, timeout: float | None = None) -> EmbeddingResponse:
        plan = self._plan()
        provider = plan.allowed_providers[0] if plan and plan.allowed_providers else ai_settings.DEFAULT_PROVIDER
        return await self._factory.get_provider(provider).embeddings(request, timeout=timeout)

    async def health_check(self) -> HealthDTO:
        plan = self._plan()
        provider = plan.allowed_providers[0] if plan and plan.allowed_providers else ai_settings.DEFAULT_PROVIDER
        return await self._factory.get_provider(provider).health_check()

    async def list_models(self) -> list[str]:
        plan = self._plan()
        if plan is not None:
            return list(plan.allowed_models)
        return await self._factory.get_provider(ai_settings.DEFAULT_PROVIDER).list_models()

    async def structured_output(
        self, request: ChatRequest, response_schema, timeout: float | None = None
    ) -> ChatResponse:
        plan = self._plan()
        if plan is None:
            instance = self._factory.get_provider(ai_settings.DEFAULT_PROVIDER)
            return await instance.structured_output(request, response_schema, timeout=timeout)
        response, provider, model = await self._selector.execute_chat(request, plan)
        return response

    async def tool_call(self, request: ChatRequest, timeout: float | None = None) -> ChatResponse:
        plan = self._plan()
        if plan is None:
            instance = self._factory.get_provider(ai_settings.DEFAULT_PROVIDER)
            return await instance.tool_call(request, timeout=timeout)
        response, provider, model = await self._selector.execute_chat(request, plan)
        return response


def default_failover_provider() -> PlanFailoverProvider:
    return PlanFailoverProvider()
