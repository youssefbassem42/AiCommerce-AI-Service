from datetime import UTC, datetime

from app.domain.widget.entities.widget_installation import WidgetInstallation
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationRepository,
)
from app.infrastructure.mongodb.collections import get_widget_installations_collection
from app.infrastructure.mongodb.documents.widget_installation_document import (
    WidgetInstallationDocument,
)
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class WidgetInstallationMongoRepository(
    BaseMongoRepository[WidgetInstallationDocument, WidgetInstallation],
    WidgetInstallationRepository,
):
    def __init__(self) -> None:
        super().__init__(get_widget_installations_collection(), WidgetInstallationDocument)

    async def find_by_public_key_hash(self, public_key_hash: str) -> WidgetInstallation | None:
        items = await self.find_many({"public_key_hash": public_key_hash}, limit=1)
        return items[0] if items else None

    async def find_by_widget_id(self, widget_id: str) -> WidgetInstallation | None:
        items = await self.find_many({"widget_id": widget_id}, limit=1)
        return items[0] if items else None

    async def find_by_store_id(self, store_id: str) -> list[WidgetInstallation]:
        return await self.find_many({"store_id": store_id})

    async def touch_last_used(self, installation_id: str) -> None:
        await self.collection.update_one(
            {"_id": installation_id},
            {"$set": {"last_used_at": datetime.now(UTC)}},
        )

    async def find_allowed_origins(self) -> set[str]:
        try:
            values = await self.collection.distinct(
                "allowed_origins",
                {"status": "active", "allowed_origins": {"$ne": []}},
            )
        except Exception:
            return set()
        origins: set[str] = set()
        for value in values:
            if isinstance(value, list):
                origins.update(o for o in value if isinstance(o, str) and o)
            elif isinstance(value, str) and value:
                origins.add(value)
        return origins
