import logging
import re

from app.application.integration.discovery.synonyms import COMMON_SYNONYMS

logger = logging.getLogger(__name__)

CANONICAL_FIELDS: dict[str, set[str]] = {
    "product": {
        "title",
        "name",
        "description",
        "price",
        "sku",
        "inventory_quantity",
        "stock",
        "images",
        "category_id",
        "vendor",
        "product_type",
        "tags",
        "weight",
        "status",
        "handle",
        "external_id",
    },
    "order": {
        "email",
        "total",
        "subtotal",
        "currency",
        "line_items",
        "financial_status",
        "fulfillment_status",
        "shipping",
        "billing",
        "notes",
        "tags",
        "customer_id",
    },
    "customer": {
        "email",
        "first_name",
        "last_name",
        "phone",
        "addresses",
        "city",
        "country",
        "zip",
        "state",
        "total_spent",
        "orders_count",
        "note",
        "tags",
    },
    "category": {
        "name",
        "title",
        "description",
        "parent_id",
        "image",
        "sort_order",
        "handle",
    },
    "inventory": {
        "product_id",
        "variant_id",
        "quantity",
        "available",
        "committed",
        "incoming",
        "location_id",
        "stock",
    },
}

FIELD_SYNONYMS: dict[str, set[str]] = {k: set(v) for k, v in COMMON_SYNONYMS.items()}


class EntityDetectionResult:
    def __init__(
        self,
        entity_type: str | None,
        confidence: float,
        matched_fields: list[str],
    ):
        self.entity_type = entity_type
        self.confidence = confidence
        self.matched_fields = matched_fields


class EntityDetector:
    """Compare external schema field names against canonical field names.

    The detector scores each entity type by:
      - exact match (weight 1.0)
      - substring match (weight 0.6)
      - synonym match (weight 0.4)
    """

    EXACT_WEIGHT = 1.0
    SUBSTRING_WEIGHT = 0.6
    SYNONYM_WEIGHT = 0.4

    def detect(self, external_fields: set[str], entity_type_hint: str | None = None) -> EntityDetectionResult:
        candidates = [entity_type_hint] if entity_type_hint else list(CANONICAL_FIELDS.keys())
        best_type: str | None = None
        best_score = 0.0
        best_matched: list[str] = []

        external_lower = {f.lower().replace("-", "_") for f in external_fields}

        for candidate in candidates:
            canonical = CANONICAL_FIELDS.get(candidate, set())
            score = 0.0
            matched: list[str] = []
            for ext_field in external_lower:
                score_contribution, match = self._score_field(ext_field, canonical)
                if score_contribution > 0:
                    score += score_contribution
                    if match:
                        matched.append(match)
            if score > best_score:
                best_score = score
                best_type = candidate
                best_matched = matched

        if best_type is None or best_score < 0.5:
            return EntityDetectionResult(
                entity_type=None,
                confidence=0.0,
                matched_fields=[],
            )

        max_possible = len(CANONICAL_FIELDS.get(best_type, set())) * self.EXACT_WEIGHT
        confidence = min(round(best_score / max_possible, 4), 1.0) if max_possible > 0 else 0.0

        return EntityDetectionResult(
            entity_type=best_type,
            confidence=confidence,
            matched_fields=list(set(best_matched)),
        )

    def _field_tokens(self, name: str) -> set[str]:
        parts = re.split(r"[_\s\-]+", name.lower())
        return {p for p in parts if len(p) > 1}

    def _has_common_token(self, a: str, b: str) -> bool:
        tokens_a = self._field_tokens(a)
        tokens_b = self._field_tokens(b)
        return bool(tokens_a & tokens_b)

    def _score_field(self, ext_field: str, canonical_set: set[str]) -> tuple[float, str | None]:
        cleaned = ext_field.replace(" ", "_").strip()
        if cleaned in canonical_set:
            return self.EXACT_WEIGHT, cleaned
        for canon in canonical_set:
            if self._has_common_token(canon, cleaned):
                return self.SUBSTRING_WEIGHT, canon
        for canon in canonical_set:
            synonyms = FIELD_SYNONYMS.get(canon, set())
            if cleaned in synonyms:
                return self.SYNONYM_WEIGHT, canon
        return 0.0, None
