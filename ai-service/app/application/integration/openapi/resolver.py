import logging
from copy import deepcopy
from typing import Any, Optional

logger = logging.getLogger(__name__)

REF_PREFIX_V3 = "#/components/schemas/"
REF_PREFIX_V2 = "#/definitions/"


class ResolvedField:
    """A single flat field with its type info."""

    def __init__(
        self,
        name: str,
        field_type: str,
        required: bool = False,
        format: Optional[str] = None,
        description: Optional[str] = None,
    ):
        self.name = name
        self.field_type = field_type
        self.required = required
        self.format = format
        self.description = description


class ResolvedSchema:
    """Result of resolving a $ref schema into a flat field list."""

    def __init__(
        self,
        fields: list[ResolvedField],
        raw_schema: dict,
        resolved_name: Optional[str] = None,
    ):
        self.fields = fields
        self.raw_schema = raw_schema
        self.resolved_name = resolved_name or "unknown"


class RefResolver:
    """Recursively resolves $ref references in an OpenAPI or Swagger spec.

    Handles allOf (merge), oneOf (pick first), anyOf (pick first).
    Provides cycle protection via a visited-set with a max depth guard.
    """

    MAX_DEPTH = 50

    def __init__(self, schemas: dict[str, dict]):
        self._schemas = schemas
        self._visited: set[str] = set()

    def resolve(self, schema: dict, depth: int = 0) -> ResolvedSchema:
        if depth > self.MAX_DEPTH:
            logger.warning("Max resolution depth (%d) reached; returning empty.", self.MAX_DEPTH)
            return ResolvedSchema(fields=[], raw_schema=schema, resolved_name="max_depth")

        if not isinstance(schema, dict):
            return ResolvedSchema(fields=[], raw_schema=schema, resolved_name="scalar")

        ref = schema.get("$ref")
        if ref:
            return self._resolve_ref(ref, depth)

        fields: list[ResolvedField] = []
        resolved_name = "inline"

        if "allOf" in schema:
            resolved_name = "allOf"
            merged: dict[str, Any] = {}
            required_set: set[str] = set()
            subs = schema.get("allOf", [])
            if isinstance(subs, list):
                for sub in subs:
                    sub_resolved = self.resolve(sub, depth + 1)
                    if sub_resolved.fields:
                        for f in sub_resolved.fields:
                            if not any(existing.name == f.name for existing in fields):
                                fields.append(f)
                    merged = self._deep_merge_schema(merged, sub_resolved.raw_schema)
                    req = sub_resolved.raw_schema.get("required", [])
                    if isinstance(req, list):
                        required_set.update(req)
            merged["required"] = list(required_set)
            return ResolvedSchema(fields=fields, raw_schema=merged, resolved_name="allOf")

        if "oneOf" in schema:
            resolved_name = "oneOf"
            members = schema.get("oneOf", [])
            first = members[0] if isinstance(members, list) and members else {}
            return self.resolve(first, depth + 1)

        if "anyOf" in schema:
            resolved_name = "anyOf"
            members = schema.get("anyOf", [])
            first = members[0] if isinstance(members, list) and members else {}
            return self.resolve(first, depth + 1)

        props = schema.get("properties", {})
        if not isinstance(props, dict):
            return ResolvedSchema(fields=fields, raw_schema=schema, resolved_name=resolved_name)

        required_fields = schema.get("required", [])
        if not isinstance(required_fields, list):
            required_fields = []

        for prop_name, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                fields.append(
                    ResolvedField(
                        name=prop_name,
                        field_type="unknown",
                        required=prop_name in required_fields,
                    )
                )
                continue

            ref = prop_schema.get("$ref")
            if ref:
                sub = self._resolve_ref(ref, depth + 1)
                if sub.fields:
                    for f in sub.fields:
                        fields.append(f)
                else:
                    fields.append(
                        ResolvedField(
                            name=prop_name,
                            field_type="object",
                            required=prop_name in required_fields,
                        )
                    )
                continue

            if prop_schema.get("properties"):
                sub_resolved = self.resolve(prop_schema, depth + 1)
                fields.append(
                    ResolvedField(
                        name=prop_name,
                        field_type="object",
                        required=prop_name in required_fields,
                    )
                )
                fields.extend(sub_resolved.fields)
                continue

            field_type = prop_schema.get("type", "string")
            fmt = prop_schema.get("format")
            fields.append(
                ResolvedField(
                    name=prop_name,
                    field_type=field_type,
                    required=prop_name in required_fields,
                    format=fmt,
                    description=prop_schema.get("description"),
                )
            )

        return ResolvedSchema(fields=fields, raw_schema=schema, resolved_name=resolved_name)

    def _resolve_ref(self, ref: str, depth: int) -> ResolvedSchema:
        if depth > self.MAX_DEPTH:
            return ResolvedSchema(fields=[], raw_schema={}, resolved_name="max_depth")

        schema_name = self._extract_schema_name(ref)
        if not schema_name:
            logger.warning("Could not extract schema name from $ref '%s'", ref)
            return ResolvedSchema(fields=[], raw_schema={}, resolved_name="invalid_ref")

        if schema_name in self._visited:
            logger.warning("Circular $ref detected for '%s'; returning empty.", schema_name)
            return ResolvedSchema(fields=[], raw_schema={}, resolved_name=schema_name)

        target = self._schemas.get(schema_name)
        if target is None:
            logger.warning("Schema '%s' not found in parsed schemas.", schema_name)
            return ResolvedSchema(fields=[], raw_schema={}, resolved_name=schema_name)

        self._visited.add(schema_name)
        result = self.resolve(target, depth + 1)
        self._visited.discard(schema_name)
        result.resolved_name = schema_name
        return result

    @staticmethod
    def _extract_schema_name(ref: str) -> Optional[str]:
        for prefix in (REF_PREFIX_V3, REF_PREFIX_V2):
            if ref.startswith(prefix):
                return ref[len(prefix):]
        if ref.startswith("#/"):
            parts = ref.split("/")
            return parts[-1] if len(parts) >= 3 else None
        return None

    @staticmethod
    def _deep_merge_schema(base: dict, override: dict) -> dict:
        result = deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = RefResolver._deep_merge_schema(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result