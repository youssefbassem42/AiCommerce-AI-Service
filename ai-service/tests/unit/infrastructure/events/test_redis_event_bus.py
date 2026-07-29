import pytest
from unittest.mock import AsyncMock, MagicMock
from redis.exceptions import ConnectionError as RedisConnectionError

from app.infrastructure.events.redis_event_bus import RedisEventBus
from app.shared.kernel.domain_event import DomainEvent


class TestRedisEvent(DomainEvent):
    data: str = "test"


@pytest.mark.asyncio
class TestRedisEventBus:
    async def test_publish_serializes_and_publishes_to_redis(self):
        redis_mock = AsyncMock()
        bus = RedisEventBus(redis_client=redis_mock, prefix="evt:")

        event = TestRedisEvent(data="redis-test")
        await bus.publish(event)

        channel = "evt:TestRedisEvent"
        redis_mock.publish.assert_called_once()
        args = redis_mock.publish.call_args
        assert args[0][0] == channel
        assert "redis-test" in args[0][1]

    async def test_publish_connection_error_raised(self):
        redis_mock = AsyncMock()
        redis_mock.publish.side_effect = RedisConnectionError("connection lost")
        bus = RedisEventBus(redis_client=redis_mock)

        with pytest.raises(RedisConnectionError):
            await bus.publish(TestRedisEvent(data="fail"))

    async def test_subscribe_stores_handler_locally(self):
        redis_mock = AsyncMock()
        bus = RedisEventBus(redis_client=redis_mock)
        handler = AsyncMock()

        await bus.subscribe(TestRedisEvent, handler)

        assert "event:TestRedisEvent" in bus._local_handlers
        assert handler in bus._local_handlers["event:TestRedisEvent"]

    async def test_unsubscribe_removes_handler(self):
        redis_mock = AsyncMock()
        bus = RedisEventBus(redis_client=redis_mock)
        handler = AsyncMock()

        await bus.subscribe(TestRedisEvent, handler)
        await bus.unsubscribe(TestRedisEvent, handler)

        assert handler not in bus._local_handlers.get("event:TestRedisEvent", [])

    async def test_custom_prefix(self):
        redis_mock = AsyncMock()
        bus = RedisEventBus(redis_client=redis_mock, prefix="custom:")

        event = TestRedisEvent(data="prefixed")
        await bus.publish(event)

        redis_mock.publish.assert_called_once_with("custom:TestRedisEvent", event.model_dump_json())
