from abc import ABC, abstractmethod
from typing import TypeVar

TEvent = TypeVar("TEvent")


class IEventHandler[TEvent](ABC):
    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        pass
