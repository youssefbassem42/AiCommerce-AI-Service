from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.ai_dto import UsageDTO
from app.application.quota.enforcer import QuotaEnforcer
from app.core.ai_exceptions import (
    ConsumerDailyLimitExceededException,
    QuotaUnavailableException,
    StoreTokenQuotaExceededException,
)

from .conftest import FakeLuaCounterStore, make_plan


@pytest.fixture
def enforcer(monkeypatch):
    plan_service = MagicMock()
    plan_service.resolve = AsyncMock(return_value=make_plan())
    consumer_quota = MagicMock()
    consumer_quota.reserve_message = AsyncMock()
    store = FakeLuaCounterStore()
    from app.application.quota.store_token_quota import StoreTokenQuotaService

    store_quota = StoreTokenQuotaService(store)
    usage_logger = MagicMock()
    usage_logger.log = AsyncMock()
    return (
        QuotaEnforcer(plan_service, consumer_quota, store_quota, usage_logger),
        plan_service,
        consumer_quota,
        store_quota,
        usage_logger,
    )


async def execute_ok(usage: UsageDTO | None = UsageDTO(prompt_tokens=100, completion_tokens=50, total_tokens=150)):
    result = MagicMock()
    result.response = "answer text"
    result.usage = usage
    return result, usage


class TestEnforcerFlow:
    async def test_reserve_commit_release_sequence(self, enforcer):
        enforcer, plan_service, consumer_quota, store_quota, usage_logger = enforcer
        consumer_quota.reserve_message.return_value = MagicMock(
            ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now()
        )

        result, usage = await enforcer.run(
            store_id="store_a",
            organization_id="org_a",
            session_id="session_1",
            echo_text="hello",
            model="gpt-4o-mini",
            execute=execute_ok,
        )
        assert usage.total_tokens == 150
        snapshot = await store_quota.snapshot(make_plan())
        assert snapshot.used == 150
        assert snapshot.reserved == 0
        usage_logger.log.assert_awaited_once()

    async def test_unused_reservation_is_released(self, enforcer):
        enforcer, _, _, store_quota, _ = enforcer
        enforcer._consumer_quota.reserve_message.return_value = MagicMock(
            ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now()
        )

        await enforcer.run(
            store_id="store_a",
            session_id="s1",
            execute=lambda: execute_ok(UsageDTO(prompt_tokens=18, completion_tokens=0, total_tokens=18)),
        )
        snapshot = await store_quota.snapshot(make_plan())
        assert snapshot.used == 18
        assert snapshot.reserved == 0

    async def test_consumer_limit_reached_rejects_before_execution(self, enforcer):
        enforcer, _, _, store_quota, usage_logger = enforcer
        from datetime import UTC, datetime

        enforcer._consumer_quota.reserve_message.return_value = MagicMock(
            ok=False, used=15, limit=15, reset_at=datetime(2026, 8, 13, tzinfo=UTC)
        )
        executed = False

        async def execute():
            nonlocal executed
            executed = True
            return None, None

        with pytest.raises(ConsumerDailyLimitExceededException) as exc_info:
            await enforcer.run(store_id="store_a", session_id="s1", execute=execute)
        assert not executed
        assert exc_info.value.code == "CONSUMER_DAILY_LIMIT_EXCEEDED"
        assert exc_info.value.limit == 15
        assert exc_info.value.used == 15

    async def test_store_quota_exceeded_rejects_before_execution(self, enforcer):
        enforcer, _, consumer_quota, store_quota, _ = enforcer
        consumer_quota.reserve_message.return_value = MagicMock(
            ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now()
        )

        small_plan = make_plan(token_limit=100)
        enforcer._plan_service.resolve = AsyncMock(return_value=small_plan)
        await store_quota.reserve(small_plan, 100)
        executed = False

        async def execute():
            nonlocal executed
            executed = True
            return None, None

        with pytest.raises(StoreTokenQuotaExceededException) as exc_info:
            await enforcer.run(
                store_id="store_a", session_id="s1", echo_text="hello", model="gpt-4o-mini", execute=execute
            )
        assert not executed
        assert exc_info.value.code == "STORE_TOKEN_QUOTA_EXCEEDED"
        assert exc_info.value.limit == 100
        assert exc_info.value.used == 0
        assert "billing_period_end" in exc_info.value.details

    async def test_failure_releases_reservation(self, enforcer):
        enforcer, _, consumer_quota, store_quota, usage_logger = enforcer
        consumer_quota.reserve_message.return_value = MagicMock(
            ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now()
        )

        async def execute():
            raise RuntimeError("provider blew up")

        with pytest.raises(RuntimeError):
            await enforcer.run(store_id="store_a", session_id="s1", echo_text="hello", execute=execute)
        snapshot = await store_quota.snapshot(make_plan())
        assert snapshot.used == 0
        assert snapshot.reserved == 0
        usage_logger.log.assert_not_awaited()

    async def test_usage_recorded_only_on_success(self, enforcer):
        enforcer, _, consumer_quota, store_quota, usage_logger = enforcer
        consumer_quota.reserve_message.return_value = MagicMock(
            ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now()
        )

        await enforcer.run(store_id="store_a", session_id="s1", echo_text="hi", execute=execute_ok)
        call = usage_logger.log.await_args.kwargs
        assert call["store_id"] == "store_a"
        assert call["billing_period"] == "2026-01"
        assert call["usage"].total_tokens == 150

    async def test_plan_not_usable_fails_closed(self, enforcer):
        enforcer, _, _, _, _ = enforcer
        enforcer._plan_service.resolve = AsyncMock(return_value=make_plan(token_limit=0))
        executed = False

        async def execute():
            nonlocal executed
            executed = True
            return None, None

        from app.application.quota.plan_policy import PlanNotAvailableError

        with pytest.raises(PlanNotAvailableError):
            await enforcer.run(store_id="store_a", execute=execute)
        assert not executed


class TestEnforcerRedisAvailability:
    async def test_redis_unavailable_fails_closed(self):
        """Spec §35: quota must not silently become unlimited."""
        failing_store = FakeLuaCounterStore(fail=True)
        plan_service = MagicMock()
        plan_service.resolve = AsyncMock(return_value=make_plan())
        consumer = MagicMock()
        consumer.reserve_message = AsyncMock(return_value=MagicMock(ok=True))
        from app.application.quota.store_token_quota import StoreTokenQuotaService

        enforcer = QuotaEnforcer(
            plan_service,
            consumer,
            StoreTokenQuotaService(failing_store),
            MagicMock(),
        )
        with pytest.raises(QuotaUnavailableException) as exc_info:
            await enforcer.run(store_id="store_a", execute=execute_ok)
        assert exc_info.value.code == "QUOTA_UNAVAILABLE"


class TestEnforcerTenantIsolation:
    async def test_store_a_and_b_never_share_quota(self):
        store = FakeLuaCounterStore()
        plan_service = MagicMock()
        plan_a = make_plan(store_id="store_a", token_limit=10_000)
        plan_b = make_plan(store_id="store_b", token_limit=10_000)

        async def resolve(store_id):
            return plan_a if store_id == "store_a" else plan_b

        plan_service.resolve = AsyncMock(side_effect=resolve)
        consumer = MagicMock()
        consumer.reserve_message = AsyncMock(
            return_value=MagicMock(ok=True, used=1, limit=15, reset_at=__import__("datetime").datetime.now())
        )
        from datetime import UTC, datetime

        consumer.reserve_message = AsyncMock(
            return_value=MagicMock(ok=True, used=1, limit=15, reset_at=datetime(2026, 8, 13, tzinfo=UTC))
        )
        from app.application.quota.store_token_quota import StoreTokenQuotaService

        store_quota = StoreTokenQuotaService(store)
        usage_logger = MagicMock()
        usage_logger.log = AsyncMock()
        enforcer = QuotaEnforcer(plan_service, consumer, store_quota, usage_logger)

        await enforcer.run(store_id="store_a", session_id="s1", echo_text="x", execute=execute_ok)
        await enforcer.run(store_id="store_b", session_id="s1", echo_text="x", execute=execute_ok)

        snap_a = await store_quota.snapshot(plan_a)
        snap_b = await store_quota.snapshot(plan_b)
        assert snap_a.used == 150
        assert snap_b.used == 150
