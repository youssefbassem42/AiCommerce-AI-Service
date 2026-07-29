from typing import Any, Dict, List
import logging

from app.shared.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    def __init__(self):
        self._handlers: Dict[type, List[Any]] = {}

    async def publish(self, event: Any) -> None:
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.debug("No handlers for event %s", type(event).__name__)
            return
        for handler in handlers:
            try:
                await handler.handle(event)
            except Exception as e:
                logger.error(
                    "Handler %s failed for %s: %s",
                    handler.__class__.__name__,
                    type(event).__name__,
                    str(e),
                )
                raise

    async def subscribe(self, event_type: type, handler: Any) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(
            "Subscribed %s to %s", handler.__class__.__name__, event_type.__name__
        )

    async def unsubscribe(self, event_type: type, handler: Any) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h is not handler
            ]
            if not self._handlers[event_type]:
                del self._handlers[event_type]
