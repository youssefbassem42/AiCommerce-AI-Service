from typing import Generic, TypeVar
from abc import ABC, abstractmethod

TEvent = TypeVar("TEvent")


class IEventHandler(ABC, Generic[TEvent]):
    @abstractmethod
    async def handle(self, event: TEvent) -> None:
        pass
