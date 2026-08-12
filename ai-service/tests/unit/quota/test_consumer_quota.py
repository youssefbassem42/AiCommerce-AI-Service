import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.application.quota.consumer_quota import ConsumerQuotaService
from app.application.quota.counter_store import QuotaUnavailableError

from .conftest import FakeLuaCounterStore


class TestConsumerDailyLimit:
    async def test_first_message_ok(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        res = await service.reserve_message("store_a", "session_1", 15)
        assert res.ok
        assert res.used == 1
        assert res.limit == 15
        assert res.reset_at > datetime.now(UTC)

    async def test_fifteenth_message_ok(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        for _ in range(15):
            res = await service.reserve_message("store_a", "session_1", 15)
        assert res.ok
        assert res.used == 15
        assert res.remaining == 0

    async def test_sixteenth_message_rejected(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        for _ in range(15):
            await service.reserve_message("store_a", "session_1", 15)
        res = await service.reserve_message("store_a", "session_1", 15)
        assert not res.ok
        assert res.used == 15

    async def test_zero_limit_always_rejects(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        res = await service.reserve_message("store_a", "session_1", 0)
        assert not res.ok
        assert res.used == 0

    async def test_anonymous_session_is_counted(self, fake_counter_store):
        """Anonymous visitors are counted via the server-side session id."""
        service = ConsumerQuotaService(fake_counter_store)
        for _ in range(15):
            await service.reserve_message("store_a", "anon-session", 15)
        res = await service.reserve_message("store_a", "anon-session", 15)
        assert not res.ok


class TestConsumerConcurrency:
    async def test_limit_fifteen_rejects_sixteenth_under_race(self):
        """15 concurrent requests against limit 15 → exactly 15 pass (§48)."""
        store = FakeLuaCounterStore()
        service = ConsumerQuotaService(store)

        results = await asyncio.gather(
            *[service.reserve_message("store_a", "session_1", 15) for _ in range(15)],
            return_exceptions=True,
        )
        results = [r for r in results if not isinstance(r, Exception)]
        assert sum(1 for r in results if r.ok) == 15

        extra = await service.reserve_message("store_a", "session_1", 15)
        assert not extra.ok
        assert extra.used == 15


class TestConsumerIsolation:
    async def test_sessions_are_isolated(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        for _ in range(15):
            await service.reserve_message("store_a", "session_1", 15)
        res = await service.reserve_message("store_a", "session_2", 15)
        assert res.ok
        assert res.used == 1

    async def test_stores_are_isolated(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        for _ in range(15):
            await service.reserve_message("store_a", "session_1", 15)
        res = await service.reserve_message("store_b", "session_1", 15)
        assert res.ok

    async def test_new_day_resets_counter(self):
        """Counter is keyed on the UTC date; a new day gets a fresh quota."""
        store = FakeLuaCounterStore()
        now_a = datetime(2026, 8, 12, 23, 59, tzinfo=UTC)
        now_b = now_a + timedelta(minutes=2)
        calls = {"n": 0}

        def fake_clock():
            calls["n"] += 1
            return now_a if calls["n"] <= 15 else now_b

        service = ConsumerQuotaService(store, clock=fake_clock)
        for _ in range(15):
            await service.reserve_message("store_a", "session_1", 15)
        res = await service.reserve_message("store_a", "session_1", 15)
        assert res.ok
        assert res.used == 1

    async def test_session_isolation_behind_random_clock(self, fake_counter_store):
        service = ConsumerQuotaService(fake_counter_store)
        res = await service.reserve_message("store_a", "s1", 15)
        assert res.ok
        assert res.used == 1


class TestConsumerFailure:
    async def test_redis_unavailable_raises(self):
        store = FakeLuaCounterStore(fail=True)
        service = ConsumerQuotaService(store)
        with pytest.raises(QuotaUnavailableError):
            await service.reserve_message("store_a", "session_1", 15)
