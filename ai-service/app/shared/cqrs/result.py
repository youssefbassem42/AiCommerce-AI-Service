from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class CommandResult[T](BaseModel):
    success: bool
    data: T | None = None
    error: str | None = None
    correlation_id: str | None = None


class QueryResult[T](BaseModel):
    success: bool
    data: T | None = None
    error: str | None = None
    correlation_id: str | None = None
