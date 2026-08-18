"""Tests for _parse_llm_json defensive parsing."""

import pytest

from app.agents.integration.tools import _parse_llm_json


def test_plain_json_parses():
    assert _parse_llm_json('{"a": 1}') == {"a": 1}


def test_markdown_fenced_json_parses():
    assert _parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_json_followed_by_prose_parses():
    assert _parse_llm_json('{"a": 1}\n\nHere is the explanation of the mapping.') == {"a": 1}


def test_json_wrapped_in_text_parses():
    assert _parse_llm_json('Sure! Here it is: {"a": 1} hope that helps') == {"a": 1}


def test_empty_response_raises():
    with pytest.raises(Exception):
        _parse_llm_json("")
