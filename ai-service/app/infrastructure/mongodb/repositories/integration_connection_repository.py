from typing import Any, Optional

from app.domain.integration.entities.integration_connection import IntegrationConnection
from app.domain.integration.repositories.integration_connection_repository import (
    IntegrationConnectionRepository as IIntegrationConnectionRepository,
)
from app.infrastructure.mongodb.collections import get_integration_connections_collection
from app.infrastructure.mongodb.documents.integration_connection_document import (
    IntegrationConnectionDocument,
)
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class IntegrationConnectionMongoRepository(
    BaseMongoRepository[IntegrationConnectionDocument, IntegrationConnection],
    IIntegrationConnectionRepository,
):

    def __init__(self):
        super().__init__(get_integration_connections_collection(), IntegrationConnectionDocument)

    async def find_by_store(
        self, store_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[IntegrationConnection], int]:
        return await self.paginate({"store_id": store_id}, page=page, page_size=page_size)

    async def find_by_store_and_name(
        self, store_id: str, name: str
    ) -> Optional[IntegrationConnection]:
        items = await self.find_many({"store_id": store_id, "name": name}, limit=1)
        return items[0] if items else None