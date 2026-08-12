"""Store token quota — atomic reservation, commit and release (spec §6-10, §15).

Flow per AI request:
    reserve(budget)  -> atomic: used + reserved + budget <= limit
    execute LLM      -> actual tokens
    commit(actual)   -> used += actual; reserved -= actual
    release(rest)    -> reserved -= rest

The final reserved/used total never exceeds the plan limit, even under
concurrency: every mutation runs as a single Redis Lua script.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings
from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.infrastructure.redis.quota_scripts import (
    CONSUMER_KEY,
    TOKEN_COMMIT_LUA,
    TOKEN_KEY,
    TOKEN_RELEASE_LUA,
    TOKEN_RESERVE_LUA,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenReservation:
    ok: bool
    key: str
    limit: int
    used: int
    reserved: int
    remaining: int
    requested: int

    @property
    def available(self) -> int:
        return max(0, self.limit - self.used - self.reserved)


@dataclass(frozen=True)
class QuotaSnapshot:
    used: int
    reserved: int


class StoreTokenQuotaService:
    """Atomic store token quota accounting over Redis."""

    def __init__(self, counter_store) -> None:
        self._store = counter_store

    async def reserve(self, plan: PlanPolicy, requested: int) -> TokenReservation:
        """Atomically reserve ``requested`` tokens under the plan limit."""
        requested = max(0, int(requested))
        key = TOKEN_KEY.format(store_id=plan.store_id, billing_period=plan.billing_period)
        ttl = settings.QUOTA_REDIS_TTL_DAYS * 86400
        result = await self._store.eval(
            TOKEN_RESERVE_LUA,
            [key],
            [plan.token_limit, requested, ttl],
        )
        ok, used, reserved, remaining = (int(v) for v in (result[0], result[1], result[2], result[3]))
        if not ok:
            logger.warning(
                "Store token quota exhausted (store=%s period=%s used=%d reserved=%d limit=%d requested=%d)",
                plan.store_id,
                plan.billing_period,
                used,
                reserved,
                plan.token_limit,
                requested,
            )
        return TokenReservation(
            ok=bool(ok),
            key=key,
            limit=plan.token_limit,
            used=used,
            reserved=reserved,
            remaining=remaining,
            requested=requested,
        )

    async def commit(self, plan: PlanPolicy, actual_tokens: int) -> QuotaSnapshot:
        """Move actual consumption into ``used`` and free the reserved portion."""
        actual_tokens = max(0, int(actual_tokens))
        key = TOKEN_KEY.format(store_id=plan.store_id, billing_period=plan.billing_period)
        ttl = settings.QUOTA_REDIS_TTL_DAYS * 86400
        result = await self._store.eval(TOKEN_COMMIT_LUA, [key], [actual_tokens, ttl])
        used, reserved = (int(v) for v in (result[0], result[1]))
        return QuotaSnapshot(used=used, reserved=reserved)

    async def release(self, plan: PlanPolicy, amount: int) -> QuotaSnapshot:
        """Release an unused reservation back to the available pool."""
        amount = max(0, int(amount))
        if amount == 0:
            snapshot = await self.snapshot(plan)
            return snapshot
        key = TOKEN_KEY.format(store_id=plan.store_id, billing_period=plan.billing_period)
        ttl = settings.QUOTA_REDIS_TTL_DAYS * 86400
        result = await self._store.eval(TOKEN_RELEASE_LUA, [key], [amount, ttl])
        used, reserved = (int(v) for v in (result[0], result[1]))
        return QuotaSnapshot(used=used, reserved=reserved)

    async def finalize(self, plan: PlanPolicy, reservation: TokenReservation, actual_tokens: int) -> QuotaSnapshot:
        """Commit actual usage and release the unused reservation (spec §15)."""
        if not reservation.ok:
            return QuotaSnapshot(used=reservation.used, reserved=reservation.reserved)
        snapshot = await self.commit(plan, actual_tokens)
        leftover = max(0, reservation.requested - actual_tokens)
        if leftover > 0:
            return await self.release(plan, leftover)
        return snapshot

    async def snapshot(self, plan: PlanPolicy) -> QuotaSnapshot:
        """Read current used/reserved counters (best effort, for reporting)."""
        key = TOKEN_KEY.format(store_id=plan.store_id, billing_period=plan.billing_period)
        try:
            result = await self._store.get(key)
            if result is None:
                return QuotaSnapshot(used=0, reserved=0)
            used, reserved = (int(v) for v in result)
            return QuotaSnapshot(used=used, reserved=reserved)
        except Exception as exc:
            logger.warning("Quota snapshot read failed (store=%s): %s", plan.store_id, exc)
            return QuotaSnapshot(used=0, reserved=0)


consumer_key = CONSUMER_KEY  # re-export for tests/consumers
