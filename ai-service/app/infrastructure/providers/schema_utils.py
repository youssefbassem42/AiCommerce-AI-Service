"""Canonical JSON-schema extraction for the structured-output contract.

``structured_output`` callers pass three kinds of ``response_schema``:

* a Pydantic model class  -> ``model_json_schema()`` (native support in
  OpenAI/Azure ``parse``, Gemini config, Claude tool input_schema);
* a plain JSON-schema dict -> passed through as-is;
* a typing construct such as ``dict[str, Any]`` (a ``types.GenericAlias``,
  which is NOT a dict and has no ``model_json_schema``) -> a permissive
  JSON object schema (``{"type": "object", "additionalProperties": true}``).

This module is the single place where that mapping happens so every
provider observes the same canonical schema regardless of how the caller
typed it.
"""

import json
from typing import Any

_PERMISSIVE_OBJECT_SCHEMA = {"type": "object", "additionalProperties": True}

_OPENAI_RESPONSE_FORMAT_TYPES = {"json_object", "json_schema", "text"}


def is_pydantic_schema(response_schema: Any) -> bool:
    """True when the value is a Pydantic model class (v1 or v2)."""
    return hasattr(response_schema, "model_json_schema") or hasattr(response_schema, "schema")


def is_generic_alias_schema(response_schema: Any) -> bool:
    """True for typing constructs like ``dict[str, Any]`` / ``list[str]``."""
    import types

    return isinstance(response_schema, types.GenericAlias)


def extract_json_schema(response_schema: Any) -> dict[str, Any]:
    """Return a canonical JSON-schema dict for any supported value.

    Pydantic models are converted via ``model_json_schema``; plain dicts
    are treated as JSON schemas already; everything else (notably the
    ``dict[str, Any]`` GenericAlias used by agents) collapses to a
    permissive JSON object schema so the structured-output contract still
    holds instead of crashing.
    """
    if hasattr(response_schema, "model_json_schema"):
        return response_schema.model_json_schema()
    if hasattr(response_schema, "schema"):
        return response_schema.schema()
    if isinstance(response_schema, dict):
        return response_schema
    return dict(_PERMISSIVE_OBJECT_SCHEMA)


def schema_description(response_schema: Any) -> str:
    """Compact JSON string of the canonical schema for prompt injection."""
    try:
        return json.dumps(extract_json_schema(response_schema))
    except (TypeError, ValueError):
        return str(response_schema)


def schema_name(response_schema: Any) -> str:
    """Stable short name for the schema (used in tool/response-format names)."""
    if isinstance(response_schema, type):
        name = getattr(response_schema, "__name__", None)
        if name:
            return name
    return "structured_output"


def is_full_response_format(response_schema: Any) -> bool:
    """True when a dict is already a complete OpenAI-style response_format
    (``{"type": "json_object" | "json_schema" | "text", ...}``) rather than
    a bare JSON schema."""
    return isinstance(response_schema, dict) and response_schema.get("type") in _OPENAI_RESPONSE_FORMAT_TYPES
