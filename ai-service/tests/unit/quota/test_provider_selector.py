from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import ChatRequest, ChatResponse, MessageDTO, UsageDTO
from app.application.quota.provider_selector import ProviderSelector
from app.core.ai_exceptions import (
    AllProvidersFailedException,
    AuthenticationException,
    ProviderUnavailableException,
    RateLimitException,
)

from .conftest import make_plan


def chat_response(model: str, provider: str) -> ChatResponse:
    return ChatResponse(
        id="r",
        message=MessageDTO(role="assistant", content="ok"),
        usage=UsageDTO(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        model=model,
        provider=provider,
        latency_ms=1.0,
    )


def make_request(model: str | None = "gpt-4o-mini") -> ChatRequest:
    return ChatRequest(messages=[MessageDTO(role="user", content="hi")], model=model or "gpt-4o-mini")


def plan_with(*, models=("gpt-4o-mini", "gemini-flash-lite-latest"), providers=("openai", "gemini")):
    return make_plan(allowed_models=models, allowed_providers=providers)


def failing(provider_name, fail_with):
    p = AsyncMock()
    p.chat = AsyncMock(side_effect=fail_with)
    return p


class TestProviderSelection:
    async def test_prefers_default_provider_first(self):
        factory = MagicMock()
        openai = AsyncMock()
        openai.chat.return_value = chat_response("gpt-4o-mini", "openai")
        gemini = AsyncMock()
        gemini.chat.return_value = chat_response("gemini-flash-lite-latest", "gemini")
        factory.get_provider.side_effect = lambda name: {"openai": openai, "gemini": gemini}[name]

        selector = ProviderSelector(factory)
        plan = plan_with()
        response, provider, model = await selector.execute_chat(make_request(), plan)
        assert provider == "openai"
        assert model == "gpt-4o-mini"

    async def test_requested_model_only_if_plan_allowed(self):
        factory = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.chat.return_value = chat_response("gpt-4o-mini", "openai")
        factory.get_provider.return_value = mock_provider

        selector = ProviderSelector(factory)
        plan = plan_with(models=("gpt-4o-mini",))
        # Consumer requests a model the plan does not allow → plan model wins.
        response, provider, model = await selector.execute_chat(make_request(model="o3-mini"), plan)
        assert model == "gpt-4o-mini"
        mock_provider.chat.assert_awaited()
        assert mock_provider.chat.await_args.args[0].model == "gpt-4o-mini"

    async def test_disallowed_provider_is_never_selected(self):
        factory = MagicMock()
        openai = AsyncMock()
        openai.chat.return_value = chat_response("gpt-4o-mini", "openai")
        factory.get_provider.side_effect = lambda name: {"openai": openai}.get(name)

        selector = ProviderSelector(factory)
        plan = plan_with(providers=("openai",))
        response, provider, model = await selector.execute_chat(make_request(), plan)
        assert provider == "openai"
        called = [c.args[0] for c in factory.get_provider.call_args_list]
        assert set(called) == {"openai"}


class TestProviderFailover:
    async def test_fails_over_to_next_allowed_provider(self):
        factory = MagicMock()
        openai = failing("openai", ProviderUnavailableException("openai", "down"))
        gemini = AsyncMock()
        gemini.chat.return_value = chat_response("gemini-flash-lite-latest", "gemini")
        factory.get_provider.side_effect = lambda name: {"openai": openai, "gemini": gemini}[name]

        selector = ProviderSelector(factory)
        response, provider, model = await selector.execute_chat(make_request(), plan_with())
        assert provider == "gemini"
        assert model == "gemini-flash-lite-latest"

    async def test_quota_exhausted_provider_triggers_failover(self):
        factory = MagicMock()
        openai = failing("openai", RateLimitException("openai", "quota exhausted"))
        gemini = AsyncMock()
        gemini.chat.return_value = chat_response("gemini-flash-lite-latest", "gemini")
        factory.get_provider.side_effect = lambda name: {"openai": openai, "gemini": gemini}[name]

        selector = ProviderSelector(factory)
        response, provider, model = await selector.execute_chat(make_request(), plan_with())
        assert provider == "gemini"

    async def test_credential_failure_triggers_failover(self):
        factory = MagicMock()
        openai = failing("openai", AuthenticationException("openai", "bad key"))
        gemini = AsyncMock()
        gemini.chat.return_value = chat_response("gemini-flash-lite-latest", "gemini")
        factory.get_provider.side_effect = lambda name: {"openai": openai, "gemini": gemini}[name]

        selector = ProviderSelector(factory)
        response, provider, model = await selector.execute_chat(make_request(), plan_with())
        assert provider == "gemini"

    async def test_all_providers_failed_raises(self):
        factory = MagicMock()
        openai = failing("openai", ProviderUnavailableException("openai", "down"))
        gemini = failing("gemini", ProviderUnavailableException("gemini", "down"))
        factory.get_provider.side_effect = lambda name: {"openai": openai, "gemini": gemini}[name]

        selector = ProviderSelector(factory)
        with pytest.raises(AllProvidersFailedException) as exc_info:
            await selector.execute_chat(make_request(), plan_with())
        assert exc_info.value.code == "AI_PROVIDER_UNAVAILABLE"

    async def test_never_fails_over_outside_plan(self):
        """Even with the default provider preferred, only plan providers run."""
        factory = MagicMock()
        claude = failing("claude", ProviderUnavailableException("claude", "down"))
        factory.get_provider.side_effect = lambda name: {"claude": claude}[name]

        selector = ProviderSelector(factory)
        plan = make_plan(allowed_models=("claude-3-5-haiku-latest",), allowed_providers=("claude",))
        with pytest.raises(AllProvidersFailedException):
            await selector.execute_chat(make_request(), plan)
        called = [c.args[0] for c in factory.get_provider.call_args_list]
        assert set(called) == {"claude"}


class TestProviderOrdering:
    def test_default_provider_first_then_plan_order(self):
        selector = ProviderSelector()
        plan = plan_with(providers=("gemini", "openai"))
        order = selector.provider_order(plan)
        assert order == ["openai", "gemini"]

    def test_provider_model_match(self):
        selector = ProviderSelector()
        plan = plan_with(models=("claude-3-5-haiku-latest", "gpt-4o-mini"), providers=("claude", "openai"))
        assert selector.model_for_provider(plan, "openai") == "gpt-4o-mini"
        assert selector.model_for_provider(plan, "claude") == "claude-3-5-haiku-latest"
