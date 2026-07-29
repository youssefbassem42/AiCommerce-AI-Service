import logging
from dataclasses import dataclass, field
from typing import Optional

from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.application.integration.mapping.transformers import get_default_registry, TransformerRegistry
from app.application.integration.discovery.entity_detector import CANONICAL_FIELDS

logger = logging.getLogger(__name__)


@dataclass
class MappingValidationIssue:
    field: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class MappingValidationResult:
    valid: bool
    issues: list[MappingValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[MappingValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[MappingValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


class MappingValidator:
    """Validates that an EntityMapping is internally consistent and complete."""

    def __init__(self, registry: Optional[TransformerRegistry] = None):
        self._registry = registry or get_default_registry()

    def validate(
        self,
        mapping: EntityMapping,
        external_schema_fields: Optional[set[str]] = None,
    ) -> MappingValidationResult:
        issues: list[MappingValidationIssue] = []

        canonical = CANONICAL_FIELDS.get(mapping.entity_type, set())

        for fm in mapping.field_mappings:
            self._validate_field_mapping(fm, external_schema_fields, canonical, issues)

        required_canonical = self._find_required_canonical(mapping)
        mapped_targets = {fm.target for fm in mapping.field_mappings}
        missing_required = required_canonical - mapped_targets
        for missing in sorted(missing_required):
            issues.append(
                MappingValidationIssue(
                    field=missing,
                    message=f"Required canonical field '{missing}' has no mapping.",
                    severity="warning",
                )
            )

        if not mapping.field_mappings:
            issues.append(
                MappingValidationIssue(
                    field="*",
                    message="No field mappings defined.",
                    severity="warning",
                )
            )

        errors = [i for i in issues if i.severity == "error"]
        return MappingValidationResult(valid=len(errors) == 0, issues=issues)

    def _validate_field_mapping(
        self,
        fm: FieldMapping,
        external_schema_fields: Optional[set[str]],
        canonical_fields: set[str],
        issues: list[MappingValidationIssue],
    ) -> None:
        if external_schema_fields:
            source_clean = fm.source.replace(" ", "_").lower()
            clean_external = {f.lower().replace("-", "_") for f in external_schema_fields}
            if source_clean not in clean_external and not source_clean.startswith("_"):
                issues.append(
                    MappingValidationIssue(
                        field=fm.source,
                        message=f"Source field '{fm.source}' not found in external schema.",
                        severity="warning",
                    )
                )

        if fm.target not in canonical_fields:
            issues.append(
                MappingValidationIssue(
                    field=fm.target,
                    message=f"Target field '{fm.target}' is not a recognized canonical field "
                            f"for entity type.",
                    severity="warning",
                )
            )

        if fm.transformer:
            if not self._registry.has(fm.transformer):
                issues.append(
                    MappingValidationIssue(
                        field=fm.source,
                        message=f"Transformer '{fm.transformer}' is not registered.",
                        severity="error",
                    )
                )

    @staticmethod
    def _find_required_canonical(mapping: EntityMapping) -> set[str]:
        required = {fm.target for fm in mapping.field_mappings if fm.required}
        base_required = {"external_id"}
        if mapping.entity_type == "product":
            base_required |= {"title", "sku"}
        elif mapping.entity_type == "order":
            base_required |= {"email", "total"}
        elif mapping.entity_type == "customer":
            base_required |= {"email"}
        return required | base_required