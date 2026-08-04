from abc import ABC, abstractmethod
from typing import Any

from app.domain.memory.entities.user_memory import UserMemory
from app.shared.kernel.repository import AsyncRepository


class MemoryRepository(AsyncRepository[UserMemory, str], ABC):
    """Domain repository interface for UserMemory entries."""

    @abstractmethod
    async def find_active_by_key(self, user_id: str, store_id: str, key: str) -> UserMemory | None:
        """Find a non-expired memory entry by its key."""
        pass

    @abstractmethod
    async def list_active(self, user_id: str, store_id: str, limit: int = 50) -> list[UserMemory]:
        """List non-expired memory entries for a user, most recently updated first."""
        pass

    @abstractmethod
    async def delete_by_key(self, user_id: str, store_id: str, key: str) -> bool:
        """Delete a memory entry by its key. Returns True if something was deleted."""
        pass

    @abstractmethod
    async def upsert(
        self,
        user_id: str,
        store_id: str,
        key: str,
        value: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> UserMemory:
        """Insert or replace a memory entry by (user_id, store_id, key) with the optional TTL."""
        pass

    @abstractmethod
    async def delete_expired(self) -> int:
        """Remove all expired memory entries. Returns the number of deleted documents."""
        pass
