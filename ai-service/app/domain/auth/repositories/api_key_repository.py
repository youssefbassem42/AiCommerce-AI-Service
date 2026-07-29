from abc import ABC, abstractmethod
from typing import Optional

from app.domain.auth.entities.api_key import ApiKey
from app.shared.kernel.repository import AsyncRepository


class ApiKeyRepository(AsyncRepository[ApiKey, str], ABC):
    """Domain repository interface for API keys."""

    @abstractmethod
    async def find_by_key_prefix(self, key_prefix: str) -> Optional[ApiKey]:
        """Find an API key by its prefix."""

    @abstractmethod
    async def find_by_store_id(self, store_id: str, limit: int = 50, skip: int = 0) -> list[ApiKey]:
        """Find all API keys for a given store/tenant."""

    @abstractmethod
    async def find_active_by_store_id(self, store_id: str) -> list[ApiKey]:
        """Find all active, non-expired API keys for a store/tenant."""
