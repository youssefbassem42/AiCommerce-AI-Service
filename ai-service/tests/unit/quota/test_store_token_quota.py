import asyncio

import pytest

from app.application.quota.counter_store import QuotaUnavailableError
from app.application.quota.store_token_quota import StoreTokenQuotaService

from .conftest import FakeLuaCounterStore, make_plan


class TestStoreTokenQuotaReservation:
    async def test_reserve_under_limit(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        res = await service.reserve(plan, 100_000)
        assert res.ok
        assert res.limit == 1_000_000
        assert res.reserved == 100_000
        assert res.remaining == 900_000

    async def test_reserve_at_limit(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        assert (await service.reserve(plan, 700_000)).ok
        res = await service.reserve(plan, 300_000)
        assert res.ok
        assert res.reserved == 1_000_000
        assert res.remaining == 0

    async def test_reserve_above_limit_rejected(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        assert (await service.reserve(plan, 900_000)).ok
        res = await service.reserve(plan, 100_001)
        assert not res.ok
        assert res.used == 0
        assert res.reserved == 900_000
        assert res.available == 100_000

    async def test_commit_moves_actual_to_used(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        res = await service.reserve(plan, 30_000)
        assert res.ok
        snapshot = await service.commit(plan, 18_000)
        assert snapshot.used == 18_000
        assert snapshot.reserved == 12_000

    async def test_release_returns_unused_reservation(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        await service.reserve(plan, 30_000)
        snapshot = await service.release(plan, 12_000)
        assert snapshot.used == 0
        assert snapshot.reserved == 18_000

    async def test_finalize_reconciliation(self, fake_counter_store):
        """Reserve 30k, actual 18k → used=18k, reserved=0 (spec §15)."""
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        reservation = await service.reserve(plan, 30_000)
        snapshot = await service.finalize(plan, reservation, 18_000)
        assert snapshot.used == 18_000
        assert snapshot.reserved == 0

    async def test_finalize_when_reservation_failed(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=100)

        await service.reserve(plan, 100)
        failed = await service.reserve(plan, 50)
        assert not failed.ok
        snapshot = await service.finalize(plan, failed, 50)
        assert snapshot.used == 0
        assert snapshot.reserved == 100

    async def test_finalize_actual_exceeds_reservation(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan = make_plan(token_limit=1_000_000)

        res = await service.reserve(plan, 10_000)
        snapshot = await service.finalize(plan, res, 10_000)
        assert snapshot.used == 10_000
        assert snapshot.reserved == 0

    async def test_commit_does_not_exceed_billing_period_rollover(self, fake_counter_store):
        """A new billing period starts a fresh counter (spec §32, §55)."""
        service = StoreTokenQuotaService(fake_counter_store)
        period_a = make_plan(billing_period="period-a", token_limit=100)
        period_b = make_plan(billing_period="period-b", token_limit=100)

        assert (await service.reserve(period_a, 100)).ok
        res_b = await service.reserve(period_b, 100)
        assert res_b.ok
        assert res_b.used == 0


class TestStoreTokenQuotaIsolation:
    async def test_store_a_does_not_consume_store_b(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan_a = make_plan(store_id="store_a", billing_period="bp", token_limit=100)
        plan_b = make_plan(store_id="store_b", billing_period="bp", token_limit=100)

        assert (await service.reserve(plan_a, 100)).ok
        res_b = await service.reserve(plan_b, 100)
        assert res_b.ok
        assert res_b.reserved == 100

    async def test_same_store_different_billing_period_is_isolated(self, fake_counter_store):
        service = StoreTokenQuotaService(fake_counter_store)
        plan_1 = make_plan(billing_period="bp-1", token_limit=100)
        plan_2 = make_plan(billing_period="bp-2", token_limit=100)

        assert (await service.reserve(plan_1, 100)).ok
        res_2 = await service.reserve(plan_2, 100)
        assert res_2.ok


class TestStoreTokenQuotaConcurrency:
    async def test_twenty_concurrent_requests_only_five_pass(self):
        """Limit 1000, 100 available, 20 concurrent × 20 tokens → 5 succeed (§48)."""
        store = FakeLuaCounterStore()
        service = StoreTokenQuotaService(store)
        plan = make_plan(token_limit=1000)

        await service.reserve(plan, 900)
        results = await asyncio.gather(
            *[service.reserve(plan, 20) for _ in range(20)],
            return_exceptions=True,
        )
        results = [r for r in results if not isinstance(r, Exception)]

        assert sum(1 for r in results if r.ok) == 5
        assert all(r.reserved <= 1000 for r in results)

        snapshot = await service.snapshot(plan)
        assert snapshot.used + snapshot.reserved == 1000


class TestStoreTokenQuotaFailure:
    async def test_redis_unavailable_fails_closed(self):
        store = FakeLuaCounterStore(fail=True)
        service = StoreTokenQuotaService(store)
        plan = make_plan()

        with pytest.raises(QuotaUnavailableError):
            await service.reserve(plan, 100)
