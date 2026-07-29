"""Tests for RedisClient wrapper."""
from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.redis.client import RedisClient


class TestRedisClient:
    """Purpose: Validate RedisClient connection and operations."""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Preconditions: None. Input: Create two instances. Execution: Compare. Expected: Same instance."""
        client1 = RedisClient()
        client2 = RedisClient()
        assert client1 is client2

    async def test_get_returns_none_when_not_connected(self):
        """Preconditions: No Redis connection. Input: Key. Execution: get(). Expected: None."""
        client = RedisClient()
        client._redis = None
        result = await client.get("test-key")
        assert result is None

    async def test_set_returns_false_when_not_connected(self):
        """Preconditions: No Redis connection. Input: Key, value. Execution: set(). Expected: False."""
        client = RedisClient()
        client._redis = None
        result = await client.set("key", "value")
        assert result is False

    async def test_delete_returns_false_when_not_connected(self):
        """Preconditions: No Redis connection. Input: Key. Execution: delete(). Expected: False."""
        client = RedisClient()
        client._redis = None
        result = await client.delete("key")
        assert result is False

    async def test_incr_returns_none_when_not_connected(self):
        """Preconditions: No Redis connection. Input: Key. Execution: incr(). Expected: None."""
        client = RedisClient()
        client._redis = None
        result = await client.incr("key")
        assert result is None

    async def test_expire_returns_false_when_not_connected(self):
        """Preconditions: No Redis connection. Input: Key, seconds. Execution: expire(). Expected: False."""
        client = RedisClient()
        client._redis = None
        result = await client.expire("key", 60)
        assert result is False

    async def test_client_property_none_when_not_connected(self):
        """Preconditions: No Redis connection. Input: None. Execution: client. Expected: None."""
        client = RedisClient()
        client._redis = None
        assert client.client is None

    async def test_pipeline_returns_none_when_not_connected(self):
        """Preconditions: No Redis connection. Input: None. Execution: pipeline(). Expected: None."""
        client = RedisClient()
        client._redis = None
        result = await client.pipeline()
        assert result is None
