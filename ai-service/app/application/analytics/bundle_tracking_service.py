import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.mongodb.collections import (
    get_bundle_tracking_collection,
    get_dashboard_insights_collection,
)

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 5
METRIC_NAME = "top_bundles"


def _make_bundle_key(product_ids: list[str], discount_pct: float) -> str:
    raw = json.dumps(sorted(product_ids), separators=(",", ":")) + f"|{discount_pct}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _config_key(store_id: str) -> str:
    return f"bundle_tracking_config:{store_id}"


class BundleTrackingService:
    def __init__(self):
        self._tracking_collection = get_bundle_tracking_collection()
        self._insights_collection = get_dashboard_insights_collection()

    async def track_copy_event(
        self,
        store_id: str,
        promo_code: str,
        product_ids: list[str],
        discount_pct: float,
        total_discount: float,
        total_original: float,
    ) -> dict[str, Any]:
        bundle_key = _make_bundle_key(product_ids, discount_pct)
        now = datetime.now(UTC)

        result = await self._tracking_collection.find_one_and_update(
            {"store_id": store_id, "bundle_key": bundle_key},
            {
                "$inc": {"copy_count": 1},
                "$set": {
                    "last_copied_at": now,
                    "promo_code": promo_code,
                    "discount_pct": discount_pct,
                    "total_discount": total_discount,
                    "total_original": total_original,
                    "product_ids": product_ids,
                },
                "$setOnInsert": {
                    "first_copied_at": now,
                    "is_top": False,
                    "promoted_at": None,
                },
            },
            upsert=True,
            return_document=True,
        )

        copy_count = result["copy_count"]
        threshold = await self._get_threshold(store_id)

        if copy_count >= threshold and not result.get("is_top"):
            await self._tracking_collection.update_one(
                {"_id": result["_id"]},
                {"$set": {"is_top": True, "promoted_at": now}},
            )
            result["is_top"] = True
            result["promoted_at"] = now
            await self._sync_to_dashboard(store_id)

        return {
            "bundle_key": bundle_key,
            "copy_count": copy_count,
            "is_top": result.get("is_top", False),
            "threshold": threshold,
        }

    async def get_tracked_bundles(
        self,
        store_id: str,
        is_top_only: bool = False,
    ) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {"store_id": store_id}
        if is_top_only:
            filters["is_top"] = True

        cursor = self._tracking_collection.find(filters).sort("copy_count", -1)
        results = []
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            results.append(doc)
        return results

    async def get_tracked_bundle(
        self,
        store_id: str,
        bundle_key: str,
    ) -> dict[str, Any] | None:
        doc = await self._tracking_collection.find_one(
            {"store_id": store_id, "bundle_key": bundle_key},
        )
        if doc:
            doc["id"] = str(doc.pop("_id"))
        return doc

    async def promote_bundle(
        self,
        store_id: str,
        bundle_key: str,
    ) -> bool:
        result = await self._tracking_collection.update_one(
            {"store_id": store_id, "bundle_key": bundle_key},
            {"$set": {"is_top": True, "promoted_at": datetime.now(UTC)}},
        )
        if result.modified_count:
            await self._sync_to_dashboard(store_id)
        return result.modified_count > 0

    async def demote_bundle(
        self,
        store_id: str,
        bundle_key: str,
    ) -> bool:
        result = await self._tracking_collection.update_one(
            {"store_id": store_id, "bundle_key": bundle_key},
            {"$set": {"is_top": False, "promoted_at": None}},
        )
        if result.modified_count:
            await self._sync_to_dashboard(store_id)
        return result.modified_count > 0

    async def get_config(self, store_id: str) -> dict[str, Any]:
        doc = await self._insights_collection.find_one(
            {"store_id": store_id, "metadata.metric_name": METRIC_NAME},
            {"metadata.tracking_config": 1},
        )
        if doc and "tracking_config" in doc.get("metadata", {}):
            return doc["metadata"]["tracking_config"]
        return {"threshold": DEFAULT_THRESHOLD, "enabled": True}

    async def update_config(
        self,
        store_id: str,
        threshold: int | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        current = await self.get_config(store_id)
        if threshold is not None:
            current["threshold"] = threshold
        if enabled is not None:
            current["enabled"] = enabled

        await self._insights_collection.update_one(
            {"store_id": store_id, "metadata.metric_name": METRIC_NAME},
            {"$set": {"metadata.tracking_config": current}},
            upsert=True,
        )
        return current

    async def _get_threshold(self, store_id: str) -> int:
        config = await self.get_config(store_id)
        return config.get("threshold", DEFAULT_THRESHOLD)

    async def _sync_to_dashboard(self, store_id: str) -> None:
        top_bundles = await self.get_tracked_bundles(store_id, is_top_only=True)
        config = await self.get_config(store_id)

        insight_data = {
            "store_id": store_id,
            "recommendations": [
                f"Bundle #{i + 1}: {', '.join(b['product_ids'])} "
                f"— copied {b['copy_count']} times "
                f"(discount: {b.get('discount_pct', 0)}%)"
                for i, b in enumerate(top_bundles)
            ],
            "metadata": {
                "metric_name": METRIC_NAME,
                "top_bundles": top_bundles,
                "tracking_config": config,
            },
            "created_at": datetime.now(UTC),
        }

        await self._insights_collection.replace_one(
            {"store_id": store_id, "metadata.metric_name": METRIC_NAME},
            insight_data,
            upsert=True,
        )
        logger.info(
            "Synced %d top bundles to dashboard for store %s",
            len(top_bundles),
            store_id,
        )
