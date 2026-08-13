import pytest
from pydantic import ValidationError
from qdrant_client.http import models

from app.infrastructure.qdrant.provider import _build_filter, _parse_conditions


class TestParseConditions:
    def test_eq_condition_with_value_format(self):
        conditions = _parse_conditions([{"key": "store_id", "value": "s1"}])
        assert len(conditions) == 1
        cond = conditions[0]
        assert isinstance(cond, models.FieldCondition)
        assert cond.key == "store_id"
        assert cond.match == models.MatchValue(value="s1")

    def test_eq_condition_with_op_and_value(self):
        conditions = _parse_conditions([{"key": "status", "op": "eq", "value": "active"}])
        assert conditions[0].match == models.MatchValue(value="active")

    def test_match_nested_dict_is_tolerated(self):
        conditions = _parse_conditions([{"key": "entity_type", "match": {"value": "product"}}])
        assert conditions[0].match == models.MatchValue(value="product")

    def test_match_value_none_raises(self):
        with pytest.raises(ValidationError):
            _parse_conditions([{"key": "store_id", "match": {"value": None}}])

    def test_build_filter_passes_through_legacy_match_format(self):
        qdrant_filter = _build_filter(
            must=[{"key": "store_id", "match": {"value": "s1"}}],
        )
        assert qdrant_filter is not None
        assert qdrant_filter.must[0].match == models.MatchValue(value="s1")

    def test_build_filter_none_when_empty(self):
        assert _build_filter() is None
        assert _build_filter(must=[]) is None
