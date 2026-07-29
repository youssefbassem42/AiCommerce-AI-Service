import logging
from typing import Optional

from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.application.integration.discovery.field_suggester import FieldSuggester, SuggestedMapping

logger = logging.getLogger(__name__)


class MappingSuggestor:
    """Suggest EntityMapping configurations by matching external fields to canonical names."""

    MIN_CONFIDENCE = 0.3

    def __init__(self, suggester: Optional[FieldSuggester] = None):
        self._suggester = suggester or FieldSuggester()

    def suggest_mappings(
        self,
        external_fields: set[str],
        entity_type: str,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> list[FieldMapping]:
        suggested: list[SuggestedMapping] = self._suggester.suggest(
            external_fields=external_fields,
            entity_type=entity_type,
        )

        result: list[FieldMapping] = []
        seen_targets: set[str] = set()
        for s in suggested:
            if s.confidence < min_confidence:
                continue
            if s.target in seen_targets:
                continue
            seen_targets.add(s.target)
            result.append(
                FieldMapping(
                    source=s.source,
                    target=s.target,
                    transformer=s.transformer,
                    required=s.target in self._get_required_fields(entity_type),
                )
            )
        return result

    @staticmethod
    def _get_required_fields(entity_type: str) -> set[str]:
        base: set[str] = {"external_id"}
        if entity_type == "product":
            base |= {"title", "sku"}
        elif entity_type == "order":
            base |= {"email", "total"}
        elif entity_type == "customer":
            base |= {"email"}
        return base


def get_required_fields(entity_type: str) -> set[str]:
    return MappingSuggestor._get_required_fields(entity_type)