import logging
from typing import Any, Optional

from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.application.integration.mapping.transformers import get_default_registry, TransformerRegistry

logger = logging.getLogger(__name__)


class MappedField:
    def __init__(
        self,
        source: str,
        target: str,
        value: Any,
        applied_transformer: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ):
        self.source = source
        self.target = target
        self.value = value
        self.applied_transformer = applied_transformer
        self.success = success
        self.error = error


class MappingReport:
    def __init__(self):
        self.fields: list[MappedField] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def mapped_count(self) -> int:
        return sum(1 for f in self.fields if f.success)


class MappedRecord:
    def __init__(
        self,
        entity_type: str,
        data: dict[str, Any],
        report: MappingReport,
    ):
        self.entity_type = entity_type
        self.data = data
        self.report = report


class MappingEngine:
    """Applies an EntityMapping to an external API item and returns a canonical record."""

    def __init__(self, registry: Optional[TransformerRegistry] = None):
        self._registry = registry or get_default_registry()

    def apply(
        self,
        external_item: dict,
        mapping: EntityMapping,
    ) -> MappedRecord:
        report = MappingReport()
        result: dict[str, Any] = {}

        for field_mapping in mapping.field_mappings:
            mf = self._apply_field(field_mapping, external_item)
            report.fields.append(mf)
            if mf.success:
                result[field_mapping.target] = mf.value
            else:
                if field_mapping.required:
                    report.errors.append(mf.error or f"Required field '{field_mapping.target}' missing.")
                else:
                    report.warnings.append(mf.error or f"Optional field '{field_mapping.target}' missing.")

        if not report.fields:
            report.warnings.append("No field mappings defined for this entity; passing through raw data.")
            return MappedRecord(
                entity_type=mapping.entity_type,
                data=dict(external_item),
                report=report,
            )

        return MappedRecord(
            entity_type=mapping.entity_type,
            data=result,
            report=report,
        )

    def _apply_field(
        self,
        field_mapping: FieldMapping,
        external_item: dict,
    ) -> MappedField:
        source_value = self._resolve_dot_notation(external_item, field_mapping.source)

        if source_value is None:
            if field_mapping.default_value is not None:
                return MappedField(
                    source=field_mapping.source,
                    target=field_mapping.target,
                    value=field_mapping.default_value,
                )
            if field_mapping.required:
                return MappedField(
                    source=field_mapping.source,
                    target=field_mapping.target,
                    value=None,
                    success=False,
                    error=f"Required source field '{field_mapping.source}' not found.",
                )
            return MappedField(
                source=field_mapping.source,
                target=field_mapping.target,
                value=None,
                success=True,
                error=f"Source field '{field_mapping.source}' not found; skipped (optional).",
            )

        if field_mapping.transformer:
            try:
                transformed = self._registry.apply(field_mapping.transformer, source_value)
                return MappedField(
                    source=field_mapping.source,
                    target=field_mapping.target,
                    value=transformed,
                    applied_transformer=field_mapping.transformer,
                )
            except Exception as e:
                logger.warning(
                    "Transformer '%s' failed on field '%s': %s. Using raw value.",
                    field_mapping.transformer,
                    field_mapping.source,
                    e,
                )
                return MappedField(
                    source=field_mapping.source,
                    target=field_mapping.target,
                    value=source_value,
                    applied_transformer=field_mapping.transformer,
                    success=False,
                    error=f"Transformer failed: {e}",
                )

        return MappedField(
            source=field_mapping.source,
            target=field_mapping.target,
            value=source_value,
        )

    @staticmethod
    def _resolve_dot_notation(item: dict, path: str) -> Any:
        parts = path.split(".")
        current: Any = item
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    idx = int(part)
                    current = current[idx] if 0 <= idx < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current