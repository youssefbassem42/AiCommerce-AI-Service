import logging
from typing import List

from app.shared.kernel.aggregate_root import AggregateRoot
from app.shared.kernel.domain_event import DomainEvent
from app.shared.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class DomainEventPublisher:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    async def flush_events(self, aggregate: AggregateRoot) -> None:
        events: List[DomainEvent] = aggregate.get_domain_events()
        if not events:
            return

        for event in events:
            try:
                await self._event_bus.publish(event)
            except Exception as e:
                logger.error(
                    "Failed to publish event %s from aggregate %s: %s",
                    type(event).__name__,
                    type(aggregate).__name__,
                    str(e),
                )
                raise

        aggregate.clear_domain_events()
