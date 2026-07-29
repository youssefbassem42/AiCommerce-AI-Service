from abc import ABC, abstractmethod
from typing import Dict, Optional
from app.shared.kernel.repository import AsyncRepository
from app.domain.recommendation.entities.store_capabilities import StoreCapabilities


class StoreCapabilitiesRepository(AsyncRepository[StoreCapabilities, str], ABC):

    @abstractmethod
    async def get_by_store_id(self, store_id: str) -> Optional[StoreCapabilities]:
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
    async def detect_capabilities(self, store_id: str) -> Dict[str, bool]:
        pass
