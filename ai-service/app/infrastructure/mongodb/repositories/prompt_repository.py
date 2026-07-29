import logging
import re
from typing import Any

from app.domain.prompt.entities.prompt import Prompt
from app.domain.prompt.repositories.prompt_repository import PromptRepository as IPromptRepository
from app.infrastructure.mongodb.collections import get_prompts_collection
from app.infrastructure.mongodb.documents.prompt_document import PromptDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository

logger = logging.getLogger(__name__)


class PromptRepository(
    BaseMongoRepository[PromptDocument, Prompt],
    IPromptRepository,
):
    def __init__(self):
        super().__init__(get_prompts_collection(), PromptDocument)

    async def create(self, entity: Prompt) -> Prompt:
        doc = PromptDocument.from_entity(entity)
        data = doc.to_mongo_dict()
        data.pop("_id", None)
        result = await self.collection.insert_one(data)
        entity.id = str(result.inserted_id)
        return entity

    async def find_by_key(self, key: str) -> Prompt | None:
        data = await self.collection.find_one({"key": key})
        if not data:
            return None
        return PromptDocument.from_mongo_dict(data).to_entity()

    async def find_by_keys(self, keys: list[str]) -> list[Prompt]:
        cursor = self.collection.find({"key": {"$in": keys}})
        results = []
        async for data in cursor:
            results.append(PromptDocument.from_mongo_dict(data).to_entity())
        return results

    async def find_by_tags(self, tags: list[str], limit: int = 100, skip: int = 0) -> list[Prompt]:
        cursor = self.collection.find({"tags": {"$in": tags}}).skip(skip).limit(limit)
        results = []
        async for data in cursor:
            results.append(PromptDocument.from_mongo_dict(data).to_entity())
        return results

    async def search(
        self,
        query: str = "",
        type_filter: str | None = None,
        tag_filter: list[str] | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> tuple[list[Prompt], int]:
        filters: dict[str, Any] = {}
        if query:
            escaped = re.escape(query)
            filters["$or"] = [
                {"key": {"$regex": escaped, "$options": "i"}},
                {"content": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
            ]
        if type_filter:
            filters["type"] = type_filter
        if tag_filter:
            filters["tags"] = {"$in": tag_filter}

        total = await self.collection.count_documents(filters)
        cursor = self.collection.find(filters).skip(skip).limit(limit)
        results = []
        async for data in cursor:
            results.append(PromptDocument.from_mongo_dict(data).to_entity())
        return results, total

    async def upsert_by_key(self, entity: Prompt) -> Prompt:
        doc = PromptDocument.from_entity(entity)
        data = doc.to_mongo_dict()
        data.pop("_id", None)
        data.pop("created_at", None)
        data["updated_at"] = data.get("updated_at", doc.updated_at)

        result = await self.collection.update_one(
            {"key": entity.key},
            {"$set": data},
            upsert=True,
        )
        if result.upserted_id:
            entity.id = str(result.upserted_id)
        else:
            existing = await self.find_by_key(entity.key)
            if existing:
                entity.id = existing.id
        return entity
