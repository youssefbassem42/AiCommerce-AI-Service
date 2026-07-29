from abc import ABC, abstractmethod
from typing import TypeVar

from app.shared.cqrs.command import Command

TCommand = TypeVar("TCommand", bound=Command)
TResult = TypeVar("TResult")


class CommandHandler[TCommand: Command, TResult](ABC):
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        pass
