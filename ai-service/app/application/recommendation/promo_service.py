import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.infrastructure.mongodb.collections import get_products_collection

logger = logging.getLogger(__name__)

PROMO_CODE_PREFIX = "BUNDLE"


class PromoCodeService:
    def __init__(self):
        self._products_collection = get_products_collection()

    async def find_existing_code(
        self,
        store_id: str,
        product_ids: List[str],
        total_discount_pct: float,
    ) -> Optional[str]:
        now = datetime.now(UTC)
        for pid in product_ids:
            doc = await self._products_collection.find_one(
                {"_id": pid, "store_id": store_id},
                {"promo_codes": 1},
            )
            if not doc:
                continue
            promo_codes: Dict = doc.get("promo_codes", {})
            for code, info in promo_codes.items():
                if isinstance(info, dict):
                    expires_at = info.get("expires_at")
                    if isinstance(expires_at, str):
                        from datetime import datetime as dt_parse
                        try:
                            expires_at = dt_parse.fromisoformat(expires_at.replace("Z", "+00:00"))
                            if expires_at.tzinfo is None:
                                expires_at = expires_at.replace(tzinfo=UTC)
                        except Exception:
                            expires_at = now
                    elif not isinstance(expires_at, datetime):
                        expires_at = now
                    elif expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)

                    if (
                        info.get("discount_pct") == total_discount_pct
                        and info.get("used") is False
                        and info.get("product_ids") == product_ids
                        and expires_at > now
                    ):
                        return code
        return None

    async def generate_code(
        self,
        store_id: str,
        product_ids: List[str],
        discount_pct: float,
        bundle_id: Optional[str] = None,
    ) -> str:
        existing = await self.find_existing_code(
            store_id=store_id,
            product_ids=product_ids,
            total_discount_pct=discount_pct,
        )
        if existing:
            logger.info("Reusing existing promo code: %s", existing)
            return existing

        code = f"{PROMO_CODE_PREFIX}-{uuid4().hex[:8].upper()}"
        promo_info = {
            "discount_pct": discount_pct,
            "product_ids": product_ids,
            "bundle_id": bundle_id,
            "used": False,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + timedelta(days=30),
        }

        for pid in product_ids:
            await self._products_collection.update_one(
                {"_id": pid, "store_id": store_id},
                {"$set": {f"promo_codes.{code}": promo_info}},
            )

        logger.info("Generated new promo code: %s for products %s", code, product_ids)
        return code

    async def redeem_code(self, code: str, store_id: str) -> bool:
        result = await self._products_collection.update_one(
            {f"promo_codes.{code}": {"$exists": True}, "store_id": store_id},
            {"$set": {f"promo_codes.{code}.used": True}},
        )
        return result.modified_count > 0
