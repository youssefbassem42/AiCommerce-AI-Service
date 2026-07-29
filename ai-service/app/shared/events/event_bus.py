from typing import Any
from abc import ABC, abstractmethod


class EventBus(ABC):
    @abstractmethod
    async def publish(self, event: Any) -> None:
        pass

    @abstractmethod
    async def subscribe(self, event_type: type, handler: Any) -> None:
        pass

    @abstractmethod
    async def unsubscribe(self, event_type: type, handler: Any) -> None:
        pass
