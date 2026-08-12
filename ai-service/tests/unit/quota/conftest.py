"""Shared fixtures for quota unit tests.

``FakeLuaCounterStore`` implements the exact semantics of the Redis Lua scripts
(app/infrastructure/redis/quota_scripts.py) in-process, serialized by an
asyncio lock so concurrent reservations behave atomically — mirroring how
Redis EVAL executes each script.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.application.quota.counter_store import QuotaUnavailableError
from app.domain.analytics.entities.plan_policy import PlanPolicy


class FakeLuaCounterStore:
    """In-memory CounterStore honoring the four quota scripts."""

    def __init__(self, fail: bool = False) -> None:
        self._lock = asyncio.Lock()
        self._token_counters: dict[str, dict] = {}
        self._consumer_counters: dict[str, int] = {}
        self.fail = fail

    async def eval(self, script: str, keys: list[str], args: list) -> list:
        if self.fail:
            raise QuotaUnavailableError("Redis unavailable")
        async with self._lock:
            if "ai:consumer" in keys[0]:
                return self._consumer_eval(keys[0], args)
            return self._token_eval(script, keys[0], args)

    def _token_eval(self, script: str, key: str, args: list) -> list:
        counter = self._token_counters.setdefault(key, {"used": 0, "reserved": 0})
        limit = int(args[0])
        if "requested" in script:
            requested = int(args[1])
            available = limit - counter["used"] - counter["reserved"]
            if available < requested:
                return [0, counter["used"], counter["reserved"], available]
            counter["reserved"] += requested
            return [1, counter["used"], counter["reserved"], limit - counter["used"] - counter["reserved"]]
        if "actual tokens" in script:
            actual = int(args[0])
            counter["used"] += actual
            counter["reserved"] = max(0, counter["reserved"] - actual)
            return [counter["used"], counter["reserved"]]
        if "to release" in script:
            amount = int(args[0])
            counter["reserved"] = max(0, counter["reserved"] - amount)
            return [counter["used"], counter["reserved"]]
        raise AssertionError(f"unknown token script: {script[:40]}")

    def _consumer_eval(self, key: str, args: list) -> list:
        limit = int(args[0])
        used = self._consumer_counters.get(key, 0)
        if limit <= 0 or used >= limit:
            return [0, used]
        self._consumer_counters[key] = used + 1
        return [1, used + 1]

    def peek(self, key: str) -> int:
        return self._consumer_counters.get(key, 0)

    async def get(self, key: str) -> tuple[int, int] | None:
        counter = self._token_counters.get(key)
        if counter is None:
            return None
        return counter["used"], counter["reserved"]


@pytest.fixture
def fake_counter_store():
    return FakeLuaCounterStore()


def make_plan(
    store_id: str = "store_a",
    token_limit: int = 1_000_000,
    billing_period: str = "2026-01",
    allowed_models=("gpt-4o-mini",),
    allowed_providers=("openai",),
    consumer_max: int = 15,
    status: str = "Active",
) -> PlanPolicy:
    now = datetime.now(UTC)
    return PlanPolicy(
        id=f"{store_id}:{billing_period}",
        store_id=store_id,
        organization_id="org_a",
        plan_name="starter",
        subscription_status=status,
        token_limit=token_limit,
        allowed_models=tuple(allowed_models),
        allowed_providers=tuple(allowed_providers),
        billing_period=billing_period,
        period_start=now,
        period_end=now + timedelta(days=30),
        consumer_daily_message_limit_max=consumer_max,
        consumer_daily_message_limit=None,
        billing_period_days=30,
    )
