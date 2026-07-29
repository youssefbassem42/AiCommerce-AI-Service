import logging
from datetime import datetime, UTC
from typing import Dict, List, Optional

from bson import ObjectId

from app.domain.recommendation.entities.store_capabilities import StoreCapabilities
from app.domain.recommendation.repositories.store_capabilities_repository import (
    StoreCapabilitiesRepository as IStoreCapabilitiesRepository,
)
from app.infrastructure.mongodb.collections import (
    get_store_capabilities_collection,
    get_integration_connections_collection,
)
from app.infrastructure.mongodb.documents.store_capabilities_document import (
    StoreCapabilitiesDocument,
)
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository

logger = logging.getLogger(__name__)

PROMO_KEYWORDS = ["promo", "coupon", "discount", "offer", "promotion"]


class StoreCapabilitiesMongoRepository(
    BaseMongoRepository[StoreCapabilitiesDocument, StoreCapabilities],
    IStoreCapabilitiesRepository,
):

    def __init__(self):
        super().__init__(get_store_capabilities_collection(), StoreCapabilitiesDocument)
        self._integrations_collection = get_integration_connections_collection()

    async def get_by_store_id(self, store_id: str) -> Optional[StoreCapabilities]:
        items = await self.find_many({"store_id": store_id}, limit=1)
        return items[0] if items else None

    async def get_or_detect(self, store_id: str) -> StoreCapabilities:
        existing = await self.get_by_store_id(store_id)
        if existing:
            needs_refresh = False
            for key, is_auto in existing.auto_detected.items():
                if is_auto:
                    needs_refresh = True
                    break
            if not needs_refresh:
                return existing

        detected = await self.detect_capabilities(store_id)

        if existing:
            for key, value in detected.items():
                if key not in existing.auto_detected or existing.auto_detected.get(key, True):
                    existing.capabilities[key] = value
                    existing.auto_detected[key] = True
            existing.updated_at = datetime.now(UTC)
            await self.update(existing)
            return existing

        entity = StoreCapabilities(
            store_id=store_id,
            capabilities=detected,
            auto_detected={k: True for k in detected},
        )
        return await self.create(entity)

    async def update_capability(
        self, store_id: str, key: str, value: bool, is_manual: bool = True
    ) -> StoreCapabilities:
        existing = await self.get_by_store_id(store_id)
        if existing:
            existing.set_capability(key, value, is_auto_detected=not is_manual)
            return await self.update(existing)

        entity = StoreCapabilities(
            store_id=store_id,
            capabilities={key: value},
            auto_detected={key: not is_manual},
        )
        return await self.create(entity)

    async def detect_capabilities(self, store_id: str) -> Dict[str, bool]:
        has_promo = False
        try:
            cursor = self._integrations_collection.find(
                {"store_id": store_id, "status": "active"},
                {"platform_name": 1},
            )
            async for doc in cursor:
                name = (doc.get("platform_name") or "").lower()
                for kw in PROMO_KEYWORDS:
                    if kw in name:
                        has_promo = True
                        break
                if has_promo:
                    break
        except Exception as e:
            logger.warning("Failed to detect capabilities for store %s: %s", store_id, e)

        return {"has_promo_codes": has_promo}
