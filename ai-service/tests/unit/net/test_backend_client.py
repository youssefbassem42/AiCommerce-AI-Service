"""Unit tests for the .NET backend plan client."""

from __future__ import annotations

import httpx
import pytest

from app.infrastructure.net.backend_client import (
    NET_PROVIDER_ALIASES,
    NetBackendClient,
    NetBackendError,
    NetDailyAllowedMessage,
    NetSubscriptionPlan,
    normalize_provider_names,
)


@pytest.fixture
def client():
    transport = httpx.MockTransport(handler=lambda request: httpx.Response(404))
    yield NetBackendClient(
        base_url="https://net.test",
        timeout=2.0,
        max_retries=1,
        transport=transport,
    )


class TestGetDailyAllowedMessage:
    async def test_parses_payload(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer tok"
            assert request.url.path == "/api/stores/s1/daily-allowed-message"
            return httpx.Response(
                200,
                json={
                    "dailyAllowedMessage": 10,
                    "planDailyAllowedMessage": 15,
                    "storeOverride": 10,
                },
            )

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        result = await net.get_daily_allowed_message("s1", "tok")
        assert result == NetDailyAllowedMessage(
            daily_allowed_message=10,
            plan_daily_allowed_message=15,
            store_override=10,
        )

    async def test_null_override_parses_as_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"dailyAllowedMessage": 7, "planDailyAllowedMessage": 15, "storeOverride": None},
            )

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        result = await net.get_daily_allowed_message("s1", "tok")
        assert result.daily_allowed_message == 7
        assert result.store_override is None

    async def test_non_2xx_raises_net_error(self, client):
        with pytest.raises(NetBackendError) as exc_info:
            await client.get_daily_allowed_message("s1", "tok")
        assert exc_info.value.status_code == 404

    async def test_network_error_retried_then_raises(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("down")

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=2,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(NetBackendError):
            await net.get_daily_allowed_message("s1", "tok")
        assert calls == 3


class TestUpdateDailyAllowedMessage:
    async def test_posts_payload(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = request.url.path
            captured["body"] = request.content
            assert request.headers["authorization"] == "Bearer tok"
            return httpx.Response(200, json={})

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        await net.update_daily_allowed_message("s1", 10, "tok")
        assert captured["url"] == "/api/stores/s1/update-daily-allowed-message"
        assert b'"dailyAllowedMessage":10' in captured["body"]

    async def test_no_retry_on_network_error(self):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("down")

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=3,
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(NetBackendError):
            await net.update_daily_allowed_message("s1", 10, "tok")
        assert calls == 1


class TestGetSubscriptionPlan:
    async def test_parses_payload_and_normalizes_providers(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/seller/subscriptions/User-Subscription-plan"
            return httpx.Response(
                200,
                json={
                    "subscriptionStatus": "Active",
                    "numOfTokens": 5_000_000,
                    "renewalDate": "2026-09-01",
                    "aiModels": ["gpt-4o-mini", "claude-haiku-4-5"],
                    "allowedProviders": ["OpenAI", "Anthropic"],
                },
            )

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        result = await net.get_subscription_plan("tok")
        assert result == NetSubscriptionPlan(
            subscription_status="Active",
            num_of_tokens=5_000_000,
            renewal_date="2026-09-01",
            ai_models=["gpt-4o-mini", "claude-haiku-4-5"],
            allowed_providers=["openai", "claude"],
        )

    async def test_missing_fields_default(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        net = NetBackendClient(
            base_url="https://net.test",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        result = await net.get_subscription_plan("tok")
        assert result.subscription_status == ""
        assert result.num_of_tokens == 0
        assert result.ai_models == []
        assert result.allowed_providers == []


class TestNormalizeProviderNames:
    def test_alias_mapping(self):
        assert normalize_provider_names(["OpenAI", "Google", "Anthropic", "gemini"]) == [
            "openai",
            "gemini",
            "claude",
        ]

    def test_comma_string(self):
        assert normalize_provider_names("openai, anthropic") == ["openai", "claude"]

    def test_unknown_kept_lowercased(self):
        assert normalize_provider_names(["Meta"]) == ["meta"]

    def test_alias_map_uses_known_identifiers(self):
        assert "openai" in NET_PROVIDER_ALIASES
        assert NET_PROVIDER_ALIASES["google"] == "gemini"
        assert NET_PROVIDER_ALIASES["anthropic"] == "claude"
