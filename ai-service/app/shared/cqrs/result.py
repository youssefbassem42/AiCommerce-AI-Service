from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class CommandResult(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None


class QueryResult(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None
