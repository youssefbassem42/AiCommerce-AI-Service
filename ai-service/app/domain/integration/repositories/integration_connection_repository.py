from abc import ABC, abstractmethod
from typing import Optional

from app.domain.integration.entities.integration_connection import IntegrationConnection
from app.shared.kernel.repository import AsyncRepository


class IntegrationConnectionRepository(AsyncRepository[IntegrationConnection, str], ABC):

    @abstractmethod
    async def find_by_store(
        self, store_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[IntegrationConnection], int]:
        pass

    @abstractmethod
    async def find_by_store_and_name(
        self, store_id: str, name: str
    ) -> Optional[IntegrationConnection]:
        pass