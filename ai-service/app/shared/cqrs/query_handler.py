from abc import ABC, abstractmethod
from typing import TypeVar

from app.shared.cqrs.query import Query

TQuery = TypeVar("TQuery", bound=Query)
TResult = TypeVar("TResult")


class QueryHandler[TQuery: Query, TResult](ABC):
    @abstractmethod
    async def handle(self, query: TQuery) -> TResult:
        pass
