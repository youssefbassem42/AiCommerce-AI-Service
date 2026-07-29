import logging
from datetime import datetime, UTC
from typing import Optional, Any

import bcrypt

from app.domain.auth.entities.api_key import ApiKey
from app.domain.auth.repositories.api_key_repository import ApiKeyRepository as IApiKeyRepository
from app.infrastructure.mongodb.collections import get_api_keys_collection
from app.infrastructure.mongodb.documents.api_key_document import ApiKeyDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository

logger = logging.getLogger(__name__)


class ApiKeyRepository(BaseMongoRepository[ApiKeyDocument, ApiKey], IApiKeyRepository):
    """MongoDB implementation of the API key repository with bcrypt hashing."""

    def __init__(self):
        super().__init__(get_api_keys_collection(), ApiKeyDocument)

    async def create(self, entity: ApiKey, session: Any = None) -> ApiKey:
        return await super().create(entity, session=session)

    async def find_by_key_prefix(self, key_prefix: str) -> Optional[ApiKey]:
        results = await self.find_many({"key_prefix": key_prefix}, limit=1)
        return results[0] if results else None

    async def find_by_store_id(
        self, store_id: str, limit: int = 50, skip: int = 0
    ) -> list[ApiKey]:
        return await self.find_many({"store_id": store_id, "deleted_at": None}, limit=limit, skip=skip)

    async def find_active_by_store_id(self, store_id: str) -> list[ApiKey]:
        now = datetime.now(UTC)
        return await self.find_many(
            {
                "store_id": store_id,
                "is_active": True,
                "deleted_at": None,
                "$or": [
                    {"expires_at": None},
                    {"expires_at": {"$gt": now}},
                ],
            }
        )

    @staticmethod
    def hash_key(raw_key: str, rounds: int = 12) -> str:
        return bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")

    @staticmethod
    def verify_key(raw_key: str, key_hash: str) -> bool:
        try:
            return bcrypt.checkpw(raw_key.encode("utf-8"), key_hash.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def generate_key_prefix(raw_key: str) -> str:
        return f"ak_{raw_key[:8]}"
