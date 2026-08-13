from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.quota.plan_policy import (
    ConsumerLimitOutOfRangeError,
    PlanNotAvailableError,
    PlanPolicyService,
    require_usable_plan,
)
from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.infrastructure.net.backend_client import (
    NetBackendError,
    NetDailyAllowedMessage,
    NetSubscriptionPlan,
)

from .conftest import make_plan


def stub_repo(policy: PlanPolicy | None = None):
    repo = MagicMock()
    repo.get_by_store = AsyncMock(return_value=policy)
    repo.upsert = AsyncMock(side_effect=lambda p: p)
    repo.update_consumer_limit = AsyncMock(return_value=None)
    return repo


def stub_net_client():
    net = MagicMock()
    net.update_daily_allowed_message = AsyncMock()
    return net


class TestPlanPolicyResolution:
    async def test_default_policy_is_bounded_not_unlimited(self):
        service = PlanPolicyService(stub_repo(None), redis_client=None)
        policy = await service.resolve("store_x")
        assert policy.token_limit > 0
        assert policy.token_limit <= 1_000_000
        assert policy.allowed_providers
        assert policy.allowed_models

    async def test_plan_not_usable_fails_closed(self):
        policy = make_plan(token_limit=0)
        with pytest.raises(PlanNotAvailableError):
            require_usable_plan(policy)

    async def test_canceled_subscription_fails_closed(self):
        policy = make_plan(status="Canceled")
        with pytest.raises(PlanNotAvailableError):
            require_usable_plan(policy)


class TestPlanClaimsSync:
    async def test_claims_override_defaults(self):
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)
        claims = {
            "subscriptionStatus": "Active",
            "numOfTokens": 5_000_000,
            "aiModels": ["gpt-4o-mini", "gemini-flash-lite-latest"],
            "planName": "pro",
            "billing_period": "bp-42",
        }
        policy = await service.sync_from_claims(claims, "store_a", "org_a")
        assert policy.token_limit == 5_000_000
        assert policy.plan_name == "pro"
        assert policy.billing_period == "bp-42"
        assert policy.store_id == "store_a"

    async def test_claimless_token_keeps_existing_policy(self):
        """A token with no plan claims must not overwrite a real entitlement."""
        existing = make_plan(token_limit=1_000_000, billing_period="bp-live")
        repo = stub_repo(existing)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_claims({}, "store_a", "org_a")
        assert policy is existing
        repo.upsert.assert_not_awaited()

    async def test_claimless_token_without_existing_uses_default(self):
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_claims({}, "store_a", "org_a")
        assert policy.token_limit > 0
        assert policy.subscription_active is True

    async def test_resolve_ignores_claimless_stored_policy(self):
        """Legacy empty policies (status '', zero limit) resolve to the usable default."""
        junk = make_plan()
        junk.subscription_status = ""
        junk.plan_name = ""
        junk.token_limit = 0
        junk.allowed_models = ()
        junk.allowed_providers = ()
        junk.billing_period = ""
        junk.renewal_date = ""
        junk.consumer_daily_message_limit_max = 0
        repo = stub_repo(junk)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.resolve("store_a")
        assert policy.token_limit > 0
        assert policy.subscription_active is True

    async def test_resolve_ignores_claimless_cached_policy(self):
        """A claim-less policy cached by an older deployment must not win."""
        junk = make_plan()
        junk.subscription_status = ""
        junk.plan_name = ""
        junk.token_limit = 0
        junk.allowed_models = ()
        junk.allowed_providers = ()
        junk.billing_period = ""
        junk.renewal_date = ""
        junk.consumer_daily_message_limit_max = 0

        redis = MagicMock()
        redis.get = AsyncMock(return_value=junk.model_dump_json())
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=redis)

        policy = await service.resolve("store_a")
        assert policy.token_limit > 0
        assert policy.subscription_active is True

    async def test_upgrade_keeps_active_billing_period_and_usage_key(self):
        """Starter 1M with 800K used → upgrade to Pro 5M keeps same period key."""
        now = datetime.now(UTC)
        existing = make_plan(token_limit=1_000_000, billing_period="bp-live")
        existing.period_start = now - timedelta(days=5)
        existing.period_end = now + timedelta(days=25)
        repo = stub_repo(existing)
        service = PlanPolicyService(repo, redis_client=None)

        claims = {
            "subscriptionStatus": "Active",
            "numOfTokens": 5_000_000,
            "aiModels": ["gpt-4o-mini"],
            "planName": "pro",
            "billing_period": "bp-live",
        }
        policy = await service.sync_from_claims(claims, "store_a", "org_a")
        assert policy.token_limit == 5_000_000
        assert policy.plan_name == "pro"
        # Same billing period → existing live quota counter keeps its usage.
        assert policy.billing_period == "bp-live"
        assert policy.period_start == existing.period_start

    async def test_expired_period_opens_new_quota_period(self):
        now = datetime.now(UTC)
        existing = make_plan(billing_period="bp-old")
        existing.period_start = now - timedelta(days=40)
        existing.period_end = now - timedelta(days=10)
        repo = stub_repo(existing)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.resolve("store_a")
        assert policy.billing_period != "bp-old"
        assert policy.period_start >= now - timedelta(minutes=5)
        assert policy.period_end > now


class TestPeriodComparison:
    async def test_legacy_naive_period_end_does_not_raise(self):
        """Stored policies from older code paths carry naive UTC datetimes;
        period comparison must treat them as UTC instead of raising."""
        now = datetime.now(UTC)
        legacy = make_plan()
        legacy.period_start = (now - timedelta(days=5)).replace(tzinfo=None)
        legacy.period_end = (now + timedelta(days=25)).replace(tzinfo=None)
        repo = stub_repo(legacy)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.resolve("store_a")
        assert policy.period_expired() is False

    async def test_legacy_naive_expired_period_rolls(self):
        now = datetime.now(UTC)
        legacy = make_plan(billing_period="bp-naive-old")
        legacy.period_start = (now - timedelta(days=40)).replace(tzinfo=None)
        legacy.period_end = (now - timedelta(days=10)).replace(tzinfo=None)
        repo = stub_repo(legacy)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.resolve("store_a")
        assert policy.billing_period != "bp-naive-old"
        assert policy.period_end > now


class TestConsumerLimit:
    async def test_store_owner_limit_within_plan_max(self):
        repo = stub_repo(make_plan(consumer_max=15))
        service = PlanPolicyService(repo, redis_client=None)
        policy = await service.set_consumer_daily_limit("store_a", 10)
        assert policy.effective_consumer_daily_limit == 10

    async def test_store_owner_limit_above_plan_max_rejected(self):
        repo = stub_repo(make_plan(consumer_max=15))
        service = PlanPolicyService(repo, redis_client=None)
        with pytest.raises(ConsumerLimitOutOfRangeError) as exc_info:
            await service.set_consumer_daily_limit("store_a", 16)
        assert exc_info.value.hard_max == 15

    async def test_effective_limit_never_exceeds_plan_max(self):
        policy = make_plan(consumer_max=15)
        policy.consumer_daily_message_limit = 99
        assert policy.effective_consumer_daily_limit == 15


class TestConsumerLimitNetWriteThrough:
    async def test_writes_through_to_net_before_local_persist(self):
        repo = stub_repo(make_plan(consumer_max=15))
        net = stub_net_client()
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.set_consumer_daily_limit("store_a", 10, net_client=net, token="tok")
        net.update_daily_allowed_message.assert_awaited_once_with("store_a", 10, "tok")
        assert policy.effective_consumer_daily_limit == 10

    async def test_no_net_write_when_no_token(self):
        repo = stub_repo(make_plan(consumer_max=15))
        net = stub_net_client()
        service = PlanPolicyService(repo, redis_client=None)

        await service.set_consumer_daily_limit("store_a", 10, net_client=net, token="")
        net.update_daily_allowed_message.assert_not_awaited()

    async def test_net_failure_fails_closed_no_local_change(self):
        repo = stub_repo(make_plan(consumer_max=15))
        net = stub_net_client()
        net.update_daily_allowed_message = AsyncMock(side_effect=NetBackendError("down", status_code=502))
        service = PlanPolicyService(repo, redis_client=None)

        with pytest.raises(NetBackendError):
            await service.set_consumer_daily_limit("store_a", 10, net_client=net, token="tok")
        repo.update_consumer_limit.assert_not_awaited()
        repo.upsert.assert_not_awaited()

    async def test_range_validation_happens_before_net_call(self):
        repo = stub_repo(make_plan(consumer_max=15))
        net = stub_net_client()
        service = PlanPolicyService(repo, redis_client=None)

        with pytest.raises(ConsumerLimitOutOfRangeError):
            await service.set_consumer_daily_limit("store_a", 16, net_client=net, token="tok")
        net.update_daily_allowed_message.assert_not_awaited()


class TestPlanNetSync:
    def _plan(self) -> NetSubscriptionPlan:
        return NetSubscriptionPlan(
            subscription_status="Active",
            num_of_tokens=5_000_000,
            renewal_date="2026-09-01",
            ai_models=["gpt-4o-mini", "claude-3-5-sonnet-latest", "bogus-model"],
            allowed_providers=["openai", "anthropic"],
        )

    async def test_upserts_policy_from_net_plan(self):
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(self._plan(), "store_a", "org_a")
        assert policy.token_limit == 5_000_000
        assert policy.subscription_status == "Active"
        assert policy.renewal_date == "2026-09-01"
        assert policy.plan_name == ""
        repo.upsert.assert_awaited_once()

    async def test_provider_allowlist_filters_models(self):
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(self._plan(), "store_a", "org_a")
        assert "gpt-4o-mini" in policy.allowed_models
        assert "claude-3-5-sonnet-latest" in policy.allowed_models
        assert "bogus-model" not in policy.allowed_models
        assert set(policy.allowed_providers) == {"openai", "claude"}

    async def test_empty_provider_allowlist_keeps_models(self):
        plan = self._plan()
        plan = NetSubscriptionPlan(
            subscription_status=plan.subscription_status,
            num_of_tokens=plan.num_of_tokens,
            renewal_date=plan.renewal_date,
            ai_models=plan.ai_models,
            allowed_providers=[],
        )
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(plan, "store_a", "org_a")
        assert "gpt-4o-mini" in policy.allowed_models
        assert "claude-3-5-sonnet-latest" in policy.allowed_models

    async def test_daily_msg_applies_override_and_plan_max(self):
        repo = stub_repo(None)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(
            self._plan(),
            "store_a",
            "org_a",
            daily_msg=NetDailyAllowedMessage(
                daily_allowed_message=12,
                plan_daily_allowed_message=50,
                store_override=12,
            ),
        )
        assert policy.consumer_daily_message_limit == 12
        assert policy.consumer_daily_message_limit_max == 50

    async def test_daily_msg_without_override_keeps_local_override(self):
        existing = make_plan(consumer_max=15)
        existing.consumer_daily_message_limit = 8
        repo = stub_repo(existing)
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(
            self._plan(),
            "store_a",
            "org_a",
            daily_msg=NetDailyAllowedMessage(
                daily_allowed_message=10,
                plan_daily_allowed_message=15,
                store_override=None,
            ),
        )
        assert policy.consumer_daily_message_limit == 8

    async def test_empty_plan_keeps_existing_policy(self):
        repo = stub_repo(make_plan(token_limit=1_000_000))
        service = PlanPolicyService(repo, redis_client=None)

        policy = await service.sync_from_net(
            NetSubscriptionPlan(subscription_status="", num_of_tokens=0, ai_models=[], allowed_providers=[]),
            "store_a",
            "org_a",
        )
        assert policy.token_limit == 1_000_000
