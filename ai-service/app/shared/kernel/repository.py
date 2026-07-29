from typing import Generic, List, Optional, Tuple, TypeVar
from abc import ABC, abstractmethod

T = TypeVar("T")
ID = TypeVar("ID")

class AsyncRepository(ABC, Generic[T, ID]):
    """Generic asynchronous repository interface."""

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Persist a new entity."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, id: ID) -> bool:
        """Delete an entity by its business ID."""
        pass

    @abstractmethod
    async def find_by_id(self, id: ID) -> Optional[T]:
        """Find an entity by its business ID."""
        pass

    @abstractmethod
    async def find_many(self, filters: dict, limit: int = 100, skip: int = 0) -> List[T]:
        """Find multiple entities matching a filter."""
        pass

    @abstractmethod
    async def paginate(
        self, filters: dict, page: int = 1, page_size: int = 20
    ) -> Tuple[List[T], int]:
        """Paginate entities matching a filter. Returns (items, total_count)."""
        pass

    @abstractmethod
    async def bulk_insert(self, entities: List[T]) -> int:
        """Bulk insert multiple entities. Returns count of inserted items."""
        pass

    @abstractmethod
    async def bulk_update(self, entities: List[T]) -> int:
        """Bulk update multiple entities. Returns count of updated items."""
        pass

    @abstractmethod
    async def exists(self, id: ID) -> bool:
        """Check if an entity exists by its business ID."""
        pass
