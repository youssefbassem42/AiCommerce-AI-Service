import pytest
from unittest.mock import AsyncMock

from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.shared.kernel.domain_event import DomainEvent


class TestEvent(DomainEvent):
    data: str = "test"


@pytest.mark.asyncio
class TestInMemoryEventBus:
    async def test_publish_with_subscriber(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()

        await bus.subscribe(TestEvent, handler)
        event = TestEvent(data="hello")
        await bus.publish(event)

        handler.handle.assert_called_once_with(event)

    async def test_publish_no_subscribers(self):
        bus = InMemoryEventBus()

        await bus.publish(TestEvent(data="hello"))

    async def test_subscribe_unsubscribe(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()

        await bus.subscribe(TestEvent, handler)
        await bus.unsubscribe(TestEvent, handler)

        await bus.publish(TestEvent(data="hello"))

        handler.handle.assert_not_called()

    async def test_multiple_handlers_for_same_event(self):
        bus = InMemoryEventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        await bus.subscribe(TestEvent, handler1)
        await bus.subscribe(TestEvent, handler2)

        event = TestEvent(data="multi")
        await bus.publish(event)

        handler1.handle.assert_called_once_with(event)
        handler2.handle.assert_called_once_with(event)

    async def test_handler_failure_raised_to_caller(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()
        handler.handle.side_effect = RuntimeError("handler failed")

        await bus.subscribe(TestEvent, handler)

        with pytest.raises(RuntimeError, match="handler failed"):
            await bus.publish(TestEvent(data="fail"))
