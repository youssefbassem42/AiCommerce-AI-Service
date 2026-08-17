"""Schema-normalization matrix for the structured-output contract.

Covers the three caller shapes (Pydantic model, JSON-schema dict,
``dict[str, Any]`` GenericAlias) plus the OpenAI response-format guard.
"""

import json
from typing import Any

import pydantic

from app.infrastructure.providers.schema_utils import (
    extract_json_schema,
    is_full_response_format,
    is_generic_alias_schema,
    is_pydantic_schema,
    schema_description,
    schema_name,
)


class IntentModel(pydantic.BaseModel):
    intent: str
    confidence: float


def test_pydantic_model_recognized_and_converted():
    assert is_pydantic_schema(IntentModel)
    assert not is_generic_alias_schema(IntentModel)
    schema = extract_json_schema(IntentModel)
    assert schema["type"] == "object"
    assert "intent" in schema["properties"]
    assert schema_name(IntentModel) == "IntentModel"


def test_plain_json_schema_dict_passed_through():
    raw = {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}
    assert not is_pydantic_schema(raw)
    assert not is_generic_alias_schema(raw)
    assert extract_json_schema(raw) == raw
    assert schema_name(raw) == "structured_output"


def test_generic_alias_recognized_and_collapsed_to_permissive_object():
    assert not is_pydantic_schema(dict[str, Any])
    assert is_generic_alias_schema(dict[str, Any])
    schema = extract_json_schema(dict[str, Any])
    assert schema == {"type": "object", "additionalProperties": True}
    assert schema_name(dict[str, Any]) == "structured_output"


def test_generic_alias_description_is_valid_json():
    desc = schema_description(dict[str, Any])
    parsed = json.loads(desc)
    assert parsed == {"type": "object", "additionalProperties": True}


def test_pydantic_description_serializes_model_json_schema():
    parsed = json.loads(schema_description(IntentModel))
    assert parsed["type"] == "object"
    assert "intent" in parsed["properties"]


def test_full_response_format_detection():
    assert is_full_response_format({"type": "json_object"})
    assert is_full_response_format({"type": "json_schema", "json_schema": {"name": "x"}})
    assert is_full_response_format({"type": "text"})
    assert not is_full_response_format({"type": "object", "properties": {}})
    assert not is_full_response_format(dict[str, Any])


def test_other_typing_constructs_collapse_to_permissive_object():
    assert extract_json_schema(list[str]) == {"type": "object", "additionalProperties": True}
    assert extract_json_schema(dict) == {"type": "object", "additionalProperties": True}
