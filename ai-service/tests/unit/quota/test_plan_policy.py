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

from .conftest import make_plan


def stub_repo(policy: PlanPolicy | None = None):
    repo = MagicMock()
    repo.get_by_store = AsyncMock(return_value=policy)
    repo.upsert = AsyncMock(side_effect=lambda p: p)
    repo.update_consumer_limit = AsyncMock(return_value=None)
    return repo


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
