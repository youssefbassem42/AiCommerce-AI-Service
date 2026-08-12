"""Consumer daily message quota — atomic, session-based, store-isolated.

Counter identity: ``store_id + session_id + day`` (spec §25). Anonymous
consumers are counted because the session identity is server-side (the widget
session token ``jti``) and never requires a trusted ``customer_id``. The
counter is scoped to the store, so a session hijacked across tenants cannot
consume another store's quota (spec §26).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.infrastructure.redis.quota_scripts import CONSUMER_KEY, CONSUMER_RESERVE_LUA

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumerReservation:
    ok: bool
    used: int
    limit: int
    reset_at: datetime

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class ConsumerQuotaService:
    """Atomic consumer daily message reservation."""

    def __init__(self, counter_store, clock=None) -> None:
        self._store = counter_store
        self._clock = clock or (lambda: datetime.now(UTC))

    async def reserve_message(self, store_id: str, session_id: str, limit: int) -> ConsumerReservation:
        """Atomically reserve one message for ``store + session + today``.

        Returns ``ok=False`` when the daily limit is reached (limit==0 always
        rejects; 15/15 rejects the 16th).
        """
        now = self._clock()
        day = now.strftime("%Y-%m-%d")
        key = CONSUMER_KEY.format(store_id=store_id, session_id=session_id, date=day)
        ttl = self._seconds_until_end_of_day(now)

        result = await self._store.eval(CONSUMER_RESERVE_LUA, [key], [int(limit), ttl])
        ok, used = (int(v) for v in (result[0], result[1]))
        reset_at = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(UTC)
        return ConsumerReservation(ok=bool(ok), used=used, limit=int(limit), reset_at=reset_at)

    def _seconds_until_end_of_day(self, now: datetime) -> int:
        midnight_utc = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
        end = (midnight_utc + timedelta(days=1)).astimezone(UTC)
        return max(60, int((end - now.astimezone(UTC)).total_seconds()) + 60)
