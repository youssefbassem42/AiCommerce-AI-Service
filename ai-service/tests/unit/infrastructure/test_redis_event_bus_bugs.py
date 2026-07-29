import pytest
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel

from app.shared.events.event_handler import IEventHandler
from app.infrastructure.events.redis_event_bus import RedisEventBus


class SampleEvent(BaseModel):
    data: str


class TestRedisEventBusBugs:

    async def test_publish_invokes_local_handlers(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="test:")
        handler = MagicMock(spec=IEventHandler)
        handler.handle = AsyncMock()

        await bus.subscribe(SampleEvent, handler)
        event = SampleEvent(data="test")
        await bus.publish(event)

        handler.handle.assert_called_once_with(event)

    async def test_publish_invokes_all_subscribed_handlers(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="test:")
        handler1 = MagicMock(spec=IEventHandler)
        handler1.handle = AsyncMock()
        handler2 = MagicMock(spec=IEventHandler)
        handler2.handle = AsyncMock()

        await bus.subscribe(SampleEvent, handler1)
        await bus.subscribe(SampleEvent, handler2)

        await bus.publish(SampleEvent(data="multi"))

        handler1.handle.assert_called_once()
        handler2.handle.assert_called_once()

    async def test_publish_sends_to_redis_and_invokes_local(self):
        redis = AsyncMock()
        redis.publish = AsyncMock()
        bus = RedisEventBus(redis_client=redis, prefix="event:")
        handler = MagicMock(spec=IEventHandler)
        handler.handle = AsyncMock()
        await bus.subscribe(SampleEvent, handler)

        event = SampleEvent(data="123")
        await bus.publish(event)

        assert redis.publish.called, "Should publish to Redis"
        handler.handle.assert_called_once_with(event)

    async def test_publish_sends_json_serialized_data(self):
        redis = AsyncMock()
        redis.publish = AsyncMock()
        bus = RedisEventBus(redis_client=redis, prefix="event:")

        event = SampleEvent(data="hello")
        await bus.publish(event)

        payload = redis.publish.call_args[0][1]
        assert '"data"' in payload
        assert '"hello"' in payload

    async def test_unsubscribe_removes_handler(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="test:")
        handler = MagicMock(spec=IEventHandler)
        handler.handle = AsyncMock()

        await bus.subscribe(SampleEvent, handler)
        await bus.unsubscribe(SampleEvent, handler)
        assert handler not in bus._local_handlers.get("test:SampleEvent", [])

    async def test_local_handlers_key_uses_prefixed_event_type(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="myapp:")
        handler = MagicMock(spec=IEventHandler)
        handler.handle = AsyncMock()

        await bus.subscribe(SampleEvent, handler)
        assert "myapp:SampleEvent" in bus._local_handlers

    async def test_unsubscribed_handler_not_invoked(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="test:")
        handler = MagicMock(spec=IEventHandler)
        handler.handle = AsyncMock()

        await bus.subscribe(SampleEvent, handler)
        await bus.unsubscribe(SampleEvent, handler)
        await bus.publish(SampleEvent(data="after-unsub"))

        handler.handle.assert_not_called()

    async def test_publish_with_no_subscribers_does_not_crash(self):
        bus = RedisEventBus(redis_client=AsyncMock(), prefix="test:")
        await bus.publish(SampleEvent(data="no-handlers"))
