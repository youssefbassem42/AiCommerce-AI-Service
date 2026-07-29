import logging
from typing import Optional, Any

from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Asynchronous Redis client wrapper with connection management."""

    _instance: Optional["RedisClient"] = None
    _redis: Optional[Redis] = None

    def __new__(cls) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def connect(self) -> None:
        if self._redis is None:
            try:
                self._redis = Redis.from_url(
                    settings.REDIS_SETTINGS.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=10,
                    retry_on_timeout=True,
                )
                await self._redis.ping()
                logger.info("Redis client connected successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._redis = None

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("Redis client disconnected.")

    @property
    def client(self) -> Optional[Redis]:
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed: {e}")
            return None

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        if not self._redis:
            return False
        try:
            await self._redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.warning(f"Redis SET failed: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self._redis:
            return False
        try:
            return await self._redis.delete(key) > 0
        except Exception as e:
            logger.warning(f"Redis DELETE failed: {e}")
            return False

    async def incr(self, key: str) -> Optional[int]:
        if not self._redis:
            return None
        try:
            return await self._redis.incr(key)
        except Exception as e:
            logger.warning(f"Redis INCR failed: {e}")
            return None

    async def expire(self, key: str, seconds: int) -> bool:
        if not self._redis:
            return False
        try:
            return await self._redis.expire(key, seconds)
        except Exception as e:
            logger.warning(f"Redis EXPIRE failed: {e}")
            return False

    async def pipeline(self, transaction: bool = True) -> Any:
        if not self._redis:
            return None
        return self._redis.pipeline(transaction=transaction)
