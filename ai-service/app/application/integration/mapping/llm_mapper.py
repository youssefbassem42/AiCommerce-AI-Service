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
   still provide a mapping with `value_source: "derive"` and a
   `default_value`, or map the closest field (the platform tolerates nulls).
4. `transformer` may be one of: lowercase, uppercase, strip, url_join,
   money_to_amount, money_to_currency, datetime_iso. Use None when no
   transformation is needed.
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
        seen: dict[str, FieldMapping] = {}
        for fm in llm_fields:
            target = fm.target.strip()
            if target not in allowed:
                continue
            source = fm.source.strip().strip("`")
            if not source or source in ("derive", "null"):
                source = "derive"
            seen[target] = FieldMapping(
                source=source,
                target=target,
                transformer=fm.transformer,
                default_value=fm.default_value,
                required=bool(fm.required),
            )
        return [seen[t] for t in allowed if t in seen]

    @staticmethod
    def fingerprint(source: Any) -> str:
        return hashlib.sha256(json.dumps(source, sort_keys=True, default=str).encode()).hexdigest()
