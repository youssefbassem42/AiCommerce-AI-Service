from abc import ABC, abstractmethod

from app.domain.recommendation.entities.store_capabilities import StoreCapabilities
from app.shared.kernel.repository import AsyncRepository


class StoreCapabilitiesRepository(AsyncRepository[StoreCapabilities, str], ABC):
    @abstractmethod
    async def get_by_store_id(self, store_id: str) -> StoreCapabilities | None:
        pass

    @abstractmethod
    async def get_or_detect(self, store_id: str) -> StoreCapabilities:
        pass

    @abstractmethod
    async def update_capability(
        self, store_id: str, key: str, value: bool, is_manual: bool = True
    ) -> StoreCapabilities:
        pass

    @abstractmethod
    async def detect_capabilities(self, store_id: str) -> dict[str, bool]:
        pass
