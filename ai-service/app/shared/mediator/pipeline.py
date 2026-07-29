from typing import Any, Callable, Awaitable
from abc import ABC, abstractmethod

NextHandler = Callable[[], Awaitable[Any]]


class PipelineBehavior(ABC):
    order: int = 0

    @abstractmethod
    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        pass
