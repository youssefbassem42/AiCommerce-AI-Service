from datetime import UTC, datetime
from typing import Any

from app.domain.memory.entities.user_memory import UserMemory
from app.domain.memory.repositories.memory_repository import MemoryRepository
from app.infrastructure.mongodb.documents.memory_document import UserMemoryDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.shared.events.event_bus import EventBus


class MongoMemoryRepository(BaseMongoRepository[UserMemoryDocument, UserMemory], MemoryRepository):
    """MongoDB implementation of the MemoryRepository interface."""

    def __init__(self, collection, event_bus: EventBus | None = None):
        super().__init__(collection, UserMemoryDocument, event_bus=event_bus)

    async def find_active_by_key(self, user_id: str, store_id: str, key: str) -> UserMemory | None:
        now = datetime.now(UTC)
        filters = {
            "user_id": user_id,
            "store_id": store_id,
            "key": key,
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }
        results = await self.find_many(filters, limit=1)
        return results[0] if results else None

    async def list_active(self, user_id: str, store_id: str, limit: int = 50) -> list[UserMemory]:
        now = datetime.now(UTC)
        filters = {
            "user_id": user_id,
            "store_id": store_id,
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }
        cursor = self.collection.find(filters).sort("updated_at", -1).limit(limit)
        results = []
        async for data in cursor:
            doc = UserMemoryDocument.from_mongo_dict(data)
            results.append(doc.to_entity())
        return results

    async def delete_by_key(self, user_id: str, store_id: str, key: str) -> bool:
        try:
            result = await self.collection.delete_one({"user_id": user_id, "store_id": store_id, "key": key})
            return result.deleted_count > 0
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def upsert(
        self,
        user_id: str,
        store_id: str,
        key: str,
        value: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> UserMemory:
        entity = UserMemory(
            user_id=user_id,
            store_id=store_id,
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
        )
        entity.touch(ttl_seconds)

        doc = UserMemoryDocument.from_entity(entity)
        data = doc.to_mongo_dict()
        data.pop("_id", None)

        now = datetime.now(UTC)
        filters = {"user_id": user_id, "store_id": store_id, "key": key}
        try:
            updated = await self.collection.find_one_and_update(
                filters,
                {
                    "$set": {
                        "value": data["value"],
                        "ttl_seconds": data.get("ttl_seconds"),
                        "expires_at": data.get("expires_at"),
                        "updated_at": data["updated_at"],
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
                return_document=True,
            )
        except Exception as e:
            self._handle_db_error(e)
            raise

        if updated:
            entity.id = str(updated["_id"])
        return entity

    async def delete_expired(self) -> int:
        now = datetime.now(UTC)
        try:
            result = await self.collection.delete_many({"expires_at": {"$lt": now}})
            return result.deleted_count
        except Exception as e:
            self._handle_db_error(e)
            raise
