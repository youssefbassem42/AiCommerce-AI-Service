import json
from typing import Any, Dict, List, Optional
import logging

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.shared.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class RedisEventBus(EventBus):
    def __init__(self, redis_client: Redis, prefix: str = "event:"):
        self._redis = redis_client
        self._prefix = prefix
        self._local_handlers: Dict[str, List[Any]] = {}

    async def publish(self, event: Any) -> None:
        event_type = type(event).__name__
        channel = f"{self._prefix}{event_type}"
        try:
            event_data = event.model_dump_json()
            await self._redis.publish(channel, event_data)
        except RedisConnectionError as e:
            logger.error("Redis connection failed during publish: %s", str(e))
            raise
        finally:
            handlers = list(self._local_handlers.get(channel, []))
            for handler in handlers:
                try:
                    await handler.handle(event)
                except Exception as e:
                    logger.error("Local handler %s failed for event %s: %s", handler, event_type, e)

    async def subscribe(self, event_type: type, handler: Any) -> None:
        key = f"{self._prefix}{event_type.__name__}"
        if key not in self._local_handlers:
            self._local_handlers[key] = []
        self._local_handlers[key].append(handler)

    async def unsubscribe(self, event_type: type, handler: Any) -> None:
        key = f"{self._prefix}{event_type.__name__}"
        if key in self._local_handlers:
            self._local_handlers[key] = [
                h for h in self._local_handlers[key] if h is not handler
            ]
            if not self._local_handlers[key]:
                del self._local_handlers[key]
