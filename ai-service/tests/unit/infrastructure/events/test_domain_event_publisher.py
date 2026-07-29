import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, UTC

from app.infrastructure.events.event_publisher import DomainEventPublisher
from app.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from app.shared.kernel.domain_event import DomainEvent
from app.shared.kernel.aggregate_root import AggregateRoot


class TestAggregate(AggregateRoot[str]):
    name: str


class TestEvent(DomainEvent):
    data: str


@pytest.mark.asyncio
class TestDomainEventPublisher:
    async def test_flush_events_publishes_and_clears(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()
        await bus.subscribe(TestEvent, handler)
        publisher = DomainEventPublisher(event_bus=bus)

        aggregate = TestAggregate(id="agg-1", name="test")
        event = TestEvent(data="flush-event")
        aggregate.add_domain_event(event)

        await publisher.flush_events(aggregate)

        handler.handle.assert_called_once_with(event)
        assert aggregate.get_domain_events() == []

    async def test_flush_events_no_events(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()
        await bus.subscribe(TestEvent, handler)
        publisher = DomainEventPublisher(event_bus=bus)

        aggregate = TestAggregate(id="agg-1", name="test")

        await publisher.flush_events(aggregate)

        handler.handle.assert_not_called()

    async def test_flush_events_publishes_multiple_events(self):
        bus = InMemoryEventBus()
        handler = AsyncMock()
        await bus.subscribe(TestEvent, handler)
        publisher = DomainEventPublisher(event_bus=bus)

        aggregate = TestAggregate(id="agg-1", name="test")
        event1 = TestEvent(data="first")
        event2 = TestEvent(data="second")
        aggregate.add_domain_event(event1)
        aggregate.add_domain_event(event2)

        await publisher.flush_events(aggregate)

        assert handler.handle.call_count == 2

    async def test_flush_events_raises_on_publish_failure(self):
        failing_bus = AsyncMock()
        failing_bus.publish.side_effect = RuntimeError("publish failed")
        publisher = DomainEventPublisher(event_bus=failing_bus)

        aggregate = TestAggregate(id="agg-1", name="test")
        event = TestEvent(data="fail")
        aggregate.add_domain_event(event)

        with pytest.raises(RuntimeError, match="publish failed"):
            await publisher.flush_events(aggregate)
