import logging
from typing import Any

from app.domain.analytics.entities.plan_policy import PlanPolicy
from app.domain.analytics.repositories.plan_policy_repository import PlanPolicyRepository as IPlanPolicyRepository
from app.infrastructure.mongodb.collections import get_store_plan_policies_collection
from app.infrastructure.mongodb.documents.store_plan_policy_document import StorePlanPolicyDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository

logger = logging.getLogger(__name__)


class PlanPolicyMongoRepository(BaseMongoRepository[StorePlanPolicyDocument, PlanPolicy], IPlanPolicyRepository):
    """MongoDB implementation of the per-store plan policy repository."""

    def __init__(self):
        super().__init__(get_store_plan_policies_collection(), StorePlanPolicyDocument)

    async def upsert(self, policy: PlanPolicy) -> PlanPolicy:
        try:
            doc = StorePlanPolicyDocument.from_entity(policy)
            await self.collection.replace_one(
                {"store_id": policy.store_id},
                doc.to_mongo_dict(),
                upsert=True,
            )
            return policy
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def get_by_store(self, store_id: str) -> PlanPolicy | None:
        try:
            doc = await self.collection.find_one({"store_id": store_id})
            if not doc:
                return None
            return StorePlanPolicyDocument.model_validate(doc, from_attributes=True).to_entity()
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def update_consumer_limit(self, store_id: str, limit: int | None) -> PlanPolicy | None:
        try:
            await self.collection.update_one(
                {"store_id": store_id},
                {"$set": {"consumer_daily_message_limit": limit, "updated_at": self._utc_now()}},
            )
            return await self.get_by_store(store_id)
        except Exception as e:
            self._handle_db_error(e)
            raise

    @staticmethod
    def _utc_now():
        from datetime import UTC, datetime

        return datetime.now(UTC)

    @classmethod
    def from_mongo_dict(cls, data: dict[str, Any]) -> StorePlanPolicyDocument:  # pragma: no cover
        return StorePlanPolicyDocument.model_validate(data, from_attributes=True)
