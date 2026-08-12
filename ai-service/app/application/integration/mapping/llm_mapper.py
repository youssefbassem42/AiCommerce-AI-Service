"""LLM-assisted entity mapping.

The mapping-time approach: the LLM receives (1) the store's OpenAPI spec,
(2) the currently configured field mapping for the entity, (3) a handful of
real sample items and (4) our documented canonical schema. It returns a
COMPLETE field mapping (dot-notation sources -> canonical targets). The
deterministic rule-based engine always remains the fallback: any failure in
this module only logs and returns the input mapping untouched.
"""

import hashlib
import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.application.integration.mapping.canonical_schema import (
    CANONICAL_SCHEMAS,
    canonical_targets,
)
from app.application.integration.mapping.transformers import get_default_registry
from app.core.ai_settings import ai_settings
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a data-integration expert for an AI commerce platform.

Your task: produce a COMPLETE field mapping between a store's external API
and the platform's canonical entity schema, so that NOT A SINGLE canonical
field is left unmapped when a sensible source field exists.

Instructions:
1. Map EVERY canonical field you can find a source for. Prefer the most
   semantically correct source, not the same-named one.
2. `source` supports dot notation for nested objects (e.g. "pricing.list").
3. When a required canonical field has no reasonable source in the item,
   still provide a mapping with `source: "derive"` and a LITERAL
   `default_value` (e.g. "active", 0, true) — never descriptive text like
   "derive from X", which would be stored verbatim — or map the closest
   field (the platform tolerates nulls).
4. `transformer` may be one of: lowercase, uppercase, trim, strip,
   string_to_decimal, string_to_int, iso_date, datetime_iso, unix_timestamp,
   split_by_comma, concat_fields, map_enum, first_image_url, money_to_amount,
   money_to_currency, url_join. Use None when no transformation is needed.
5. NEVER invent fake `source` paths that do not appear in the item samples;
   when unsure, map to the closest real key.
6. `required: true` ONLY when the canonical field is required AND the source
   is present on every sample item.
7. Keep the total mapping compact but complete: one entry per canonical field
   that has a source or a sensible default.
"""


class LLMFieldMapping(BaseModel):
    source: str = Field(..., min_length=1, max_length=256)
    target: str = Field(..., min_length=1, max_length=128)
    transformer: str | None = None
    default_value: Any = None
    required: bool = False


class LLMMappingResult(BaseModel):
    entity_type: str = ""
    field_mappings: list[LLMFieldMapping] = Field(default_factory=list)


class LlmEntityMapper:
    def __init__(
        self,
        provider_factory: LLMProviderFactory | None = None,
        provider_name: str | None = os.getenv("LLM_MAPPING_PROVIDER") or None,
        model: str | None = os.getenv("LLM_MAPPING_MODEL") or None,
        enabled: bool = os.getenv("LLM_MAPPING_ENABLED", "true").lower() not in ("0", "false", "no"),
        max_sample_items: int = int(os.getenv("LLM_MAPPING_SAMPLE_ITEMS", "5")),
        timeout: float = 60.0,
    ):
        self._factory = provider_factory or LLMProviderFactory()
        self._provider_name = provider_name
        self._model = model
        self.enabled = enabled
        self.max_sample_items = max(1, max_sample_items)
        self.timeout = timeout

    async def build_entity_mapping(
        self,
        entity_type: str,
        current: EntityMapping,
        raw_spec: dict[str, Any],
        sample_items: list[dict[str, Any]],
    ) -> EntityMapping | None:
        """Return an updated EntityMapping with LLM-produced field mappings.

        Returns ``None`` when the LLM is disabled, unconfigured, or failed —
        the caller then falls back to rule-based mapping unchanged.
        """
        if not self.enabled:
            return None
        if entity_type not in CANONICAL_SCHEMAS:
            logger.info("No canonical schema for entity '%s'; skipping LLM mapping.", entity_type)
            return None
        if not sample_items:
            return None

        try:
            provider = self._factory.get_provider(self._provider_name or ai_settings.DEFAULT_PROVIDER)
            request = self._build_request(entity_type, current, raw_spec, sample_items)
            response = await provider.structured_output(request, LLMMappingResult, timeout=self.timeout)
        except Exception as e:
            logger.warning("LLM mapping failed for entity '%s': %s — using rule engine.", entity_type, e)
            return None

        try:
            if isinstance(response, dict):
                parsed = LLMMappingResult.model_validate(response)
            else:
                content = getattr(response, "message", None)
                content = getattr(content, "content", None)
                if isinstance(content, str):
                    parsed = LLMMappingResult.model_validate_json(content)
                else:
                    parsed = LLMMappingResult.model_validate(response)
        except Exception as e:
            logger.warning("LLM mapping response invalid for entity '%s': %s", entity_type, e)
            return None

        fields = self._sanitize_mappings(entity_type, parsed.field_mappings)
        if not fields:
            logger.warning("LLM returned no valid mapping for entity '%s'.", entity_type)
            return None

        return current.model_copy(update={"field_mappings": fields})

    def _build_request(
        self,
        entity_type: str,
        current: EntityMapping,
        raw_spec: dict[str, Any],
        sample_items: list[dict[str, Any]],
    ) -> ChatRequest:
        existing = [
            {
                "source": fm.source,
                "target": fm.target,
                "transformer": fm.transformer,
                "required": fm.required,
            }
            for fm in current.field_mappings
        ]
        items = [dict(item) for item in sample_items[: self.max_sample_items]]
        user_payload = {
            "entity_type": entity_type,
            "openapi_spec": self._truncate_spec(raw_spec, 40000),
            "current_field_mapping": existing,
            "sample_items": items,
            "requested_output": {
                "entity_type": entity_type,
                "field_mappings": [
                    {
                        "source": "dot-notation key from the API item (or 'derive')",
                        "target": "canonical target field",
                        "transformer": "one of the listed transformers or null",
                        "default_value": "only when deriving",
                        "required": "boolean",
                    }
                ],
            },
        }
        system = MessageDTO(
            role="system",
            content=SYSTEM_PROMPT + "\n\nCANONICAL SCHEMAS:\n" + json.dumps(CANONICAL_SCHEMAS, indent=2),
        )
        user = MessageDTO(role="user", content=json.dumps(user_payload, indent=2, default=str))
        return ChatRequest(
            messages=[system, user],
            model=self._model or ai_settings.DEFAULT_MODEL,
            temperature=0,
        )

    @staticmethod
    def _truncate_spec(spec: dict[str, Any], limit: int) -> dict[str, Any]:  # noqa: ARG004
        if not isinstance(spec, dict):
            return {}
        paths = spec.get("paths", {})
        components = spec.get("components") if isinstance(spec.get("components"), dict) else {}
        schemas_container = components.get("schemas", {})
        return {"paths": paths, "schemas": schemas_container}

    def _sanitize_mappings(
        self,
        entity_type: str,
        llm_fields: list[LLMFieldMapping],
    ) -> list[FieldMapping]:
        allowed = canonical_targets(entity_type)
        if not allowed:
            return []
        registry = get_default_registry()
        seen: dict[str, FieldMapping] = {}
        for fm in llm_fields:
            target = fm.target.strip()
            if target not in allowed:
                continue
            source = fm.source.strip().strip("`")
            if not source or source in ("null", "None"):
                continue

            transformer = fm.transformer
            if transformer and not registry.has(transformer):
                logger.warning(
                    "Dropping unknown transformer '%s' on field '%s' (entity '%s').",
                    transformer,
                    target,
                    entity_type,
                )
                transformer = None

            if source == "derive":
                default = fm.default_value
                if not self._is_constant_default(default):
                    logger.warning(
                        "Dropping derive field '%s' whose default '%s' is not a literal constant.",
                        target,
                        default,
                    )
                    continue
                seen[target] = FieldMapping(
                    source="derive",
                    target=target,
                    transformer=transformer,
                    default_value=default,
                    required=bool(fm.required),
                )
                continue

            seen[target] = FieldMapping(
                source=source,
                target=target,
                transformer=transformer,
                default_value=fm.default_value,
                required=bool(fm.required),
            )
        return [seen[t] for t in allowed if t in seen]

    @staticmethod
    def _is_constant_default(value: Any) -> bool:
        """True when a derive default is a literal constant (not descriptive text)."""
        if value is None or isinstance(value, (bool, int, float)):
            return True
        if isinstance(value, str):
            text = value.strip()
            if len(text) > 60 or "derive" in text.lower():
                return False
            return bool(text)
        return False

    def sanitize_entity_mapping(self, mapping: EntityMapping) -> EntityMapping:
        """Re-validate a persisted mapping against the canonical schema and registry.

        Used for cached/LLM-built mappings stored on the connection: unknown
        transformers are dropped (fields keep their raw values) and derive
        fields with descriptive pseudo-defaults (e.g. "derive from title") are
        removed instead of being written as literal junk.
        """
        if not mapping.field_mappings:
            return mapping
        registry = get_default_registry()
        cleaned: list[FieldMapping] = []
        for fm in mapping.field_mappings:
            transformer = fm.transformer
            if transformer and not registry.has(transformer):
                logger.warning(
                    "Dropping unknown transformer '%s' on field '%s' (entity '%s').",
                    transformer,
                    fm.target,
                    mapping.entity_type,
                )
                transformer = None
            if fm.source == "derive" and not LlmEntityMapper._is_constant_default(fm.default_value):
                logger.warning(
                    "Dropping derive field '%s' with non-literal default '%s' (entity '%s').",
                    fm.target,
                    fm.default_value,
                    mapping.entity_type,
                )
                continue
            if not fm.source or fm.source in ("null", "None"):
                continue
            cleaned.append(
                FieldMapping(
                    source=fm.source,
                    target=fm.target,
                    transformer=transformer,
                    default_value=fm.default_value,
                    required=fm.required,
                )
            )
        if len(cleaned) == len(mapping.field_mappings):
            return mapping
        return mapping.model_copy(update={"field_mappings": cleaned})

    @staticmethod
    def fingerprint(source: Any) -> str:
        return hashlib.sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()
