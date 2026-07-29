import logging
import re
from dataclasses import dataclass

from app.application.integration.discovery.synonyms import COMMON_SYNONYMS

logger = logging.getLogger(__name__)

SYNONYM_MAP: dict[str, list[str]] = {k: sorted(v) for k, v in COMMON_SYNONYMS.items()}


@dataclass
class SuggestedMapping:
    source: str
    target: str
    confidence: float
    transformer: str | None = None

    def __hash__(self):
        return hash((self.source, self.target))


class FieldSuggester:
    """Suggest field mappings by name similarity."""

    EXACT_SCORE = 1.0
    SYNONYM_SCORE = 0.7
    SUBSTRING_SCORE = 0.5

    @staticmethod
    def _field_tokens(name: str) -> set[str]:
        parts = re.split(r"[_\s\-]+", name.lower())
        return {p for p in parts if len(p) > 1}

    @staticmethod
    def _has_common_token(a: str, b: str) -> bool:
        tokens_a = FieldSuggester._field_tokens(a)
        tokens_b = FieldSuggester._field_tokens(b)
        return bool(tokens_a & tokens_b)

    def suggest(self, external_fields: set[str], entity_type: str) -> list[SuggestedMapping]:
        from app.application.integration.discovery.entity_detector import CANONICAL_FIELDS

        canonical = CANONICAL_FIELDS.get(entity_type, set())
        results: list[SuggestedMapping] = []

        if not canonical:
            return self._suggest_identity_mappings(external_fields)

        for ext_field in external_fields:
            ext_clean = ext_field.lower().replace("-", "_").strip()

            best_match: str | None = None
            best_confidence = 0.0
            transformer_hint: str | None = None

            for canon in canonical:
                if ext_clean == canon:
                    if best_confidence < self.EXACT_SCORE:
                        best_confidence = self.EXACT_SCORE
                        best_match = canon
                    continue

                if ext_clean in SYNONYM_MAP.get(canon, []):
                    score = self.SYNONYM_SCORE
                    if score > best_confidence:
                        best_confidence = score
                        best_match = canon
                    continue

                if self._has_common_token(canon, ext_clean):
                    if best_confidence < self.SUBSTRING_SCORE:
                        best_confidence = self.SUBSTRING_SCORE
                        best_match = canon
                    continue

            if best_match:
                if best_match in ("price", "cost", "amount"):
                    transformer_hint = "string_to_decimal"
                elif "date" in best_match:
                    transformer_hint = "iso_date"
                results.append(
                    SuggestedMapping(
                        source=ext_field,
                        target=best_match,
                        confidence=best_confidence,
                        transformer=transformer_hint,
                    )
                )

        return results

    @staticmethod
    def _suggest_identity_mappings(external_fields: set[str]) -> list[SuggestedMapping]:
        """For unknown entity types create identity mappings so raw data is preserved."""
        id_field = None
        for candidate in ("id", "external_id", "source_id", "remote_id"):
            if candidate in external_fields or candidate.replace("_", "") in {
                f.replace("_", "") for f in external_fields
            }:
                id_field = candidate
                break
        results: list[SuggestedMapping] = []
        for f in external_fields:
            results.append(
                SuggestedMapping(
                    source=f,
                    target=f,
                    confidence=1.0,
                    transformer=None,
                )
            )
            if f == id_field:
                results.append(
                    SuggestedMapping(
                        source=f,
                        target="external_id",
                        confidence=0.8,
                        transformer=None,
                    )
                )
        return results
