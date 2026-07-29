from typing import Any
import logging

from app.shared.kernel.aggregate_root import AggregateRoot
from app.shared.mediator.pipeline import PipelineBehavior, NextHandler
from app.shared.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class EventPublisherBehavior(PipelineBehavior):
    order: int = 2000

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        result = await next_handler()

        if isinstance(result, AggregateRoot):
            events = result.get_domain_events()
            if events:
                for event in events:
                    try:
                        await self._event_bus.publish(event)
                    except Exception as e:
                        logger.error(
                            "Failed to publish event %s: %s",
                            type(event).__name__,
                            str(e),
                        )
                result.clear_domain_events()

        return result
