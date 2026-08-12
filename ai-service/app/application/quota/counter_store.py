"""Quota counter store — the atomic Redis backend for enforcement.

Fail-closed by design: when Redis is unavailable the store raises
``QuotaUnavailableError`` instead of silently allowing unlimited AI usage
(spec §35). ``QUOTA_FAIL_OPEN`` exists only as an explicit operator override
and is disabled by default.
"""

import logging
from contextlib import suppress
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class QuotaUnavailableError(Exception):
    """Redis is unavailable and quota enforcement cannot proceed safely."""


class CounterStore(Protocol):
    async def eval(self, script: str, keys: list[str], args: list) -> list: ...


class RedisQuotaCounterStore:
    """Executes quota Lua scripts against Redis (lazy connection, fail closed)."""

    def __init__(self, url: str | None = None, fail_open: bool | None = None) -> None:
        self._url = url or settings.REDIS_SETTINGS.REDIS_URL
        self._fail_open = settings.QUOTA_FAIL_OPEN if fail_open is None else fail_open
        self._redis: Redis | None = None

    async def eval(self, script: str, keys: list[str], args: list) -> list:
        redis = await self._get_redis()
        if redis is None:
            return self._on_redis_unavailable()
        try:
            result = await redis.eval(script, len(keys), *keys, *args)
            if result is None:
                raise QuotaUnavailableError("Redis EVAL returned no result")
            return list(result) if isinstance(result, (list, tuple)) else [result]
        except QuotaUnavailableError:
            raise
        except Exception as exc:
            logger.error("Quota Redis EVAL failed: %s", exc)
            return self._on_redis_unavailable()

    async def get(self, key: str) -> tuple[int, int] | None:
        redis = await self._get_redis()
        if redis is None:
            raise QuotaUnavailableError("Redis unavailable for quota read")
        try:
            raw = await redis.hgetall(key)
            if not raw:
                return None
            used = int(raw.get("used", 0) or 0)
            reserved = int(raw.get("reserved", 0) or 0)
            return used, reserved
        except QuotaUnavailableError:
            raise
        except Exception as exc:
            logger.error("Quota Redis read failed: %s", exc)
            raise QuotaUnavailableError("Redis unavailable for quota read") from exc

    async def _get_redis(self) -> Redis | None:
        if self._redis is not None:
            return self._redis
        try:
            self._redis = Redis.from_url(
                self._url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=5,
            )
            await self._redis.ping()
            return self._redis
        except Exception as exc:
            logger.error("Quota Redis connection failed: %s", exc)
            self._redis = None
            return None

    async def close(self) -> None:
        if self._redis is not None:
            with suppress(Exception):
                await self._redis.aclose()
            self._redis = None

    def _on_redis_unavailable(self) -> list:
        if self._fail_open:
            logger.error("QUOTA FAIL-OPEN ENABLED — commercial quota bypassed (operator override)")
            return [1, 0, 0, 0]
        raise QuotaUnavailableError("Redis unavailable — quota enforcement failed closed")
