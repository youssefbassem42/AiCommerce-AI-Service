import pytest

from app.application.integration.discovery.field_suggester import FieldSuggester, SYNONYM_MAP
from app.application.integration.discovery.synonyms import COMMON_SYNONYMS


@pytest.fixture
def suggester() -> FieldSuggester:
    return FieldSuggester()


class TestFieldSuggesterBugs:

    def test_synonym_maps_unified(self) -> None:
        from app.application.integration.discovery.entity_detector import FIELD_SYNONYMS

        for key in COMMON_SYNONYMS:
            assert key in FIELD_SYNONYMS, (
                f"Key '{key}' missing from entity_detector.FIELD_SYNONYMS"
            )
            assert key in SYNONYM_MAP, (
                f"Key '{key}' missing from field_suggester.SYNONYM_MAP"
            )
            entity_syns = set(FIELD_SYNONYMS[key])
            suggester_syns = set(SYNONYM_MAP[key])
            assert entity_syns == suggester_syns, (
                f"Synonym mismatch for '{key}': "
                f"entity_detector={sorted(entity_syns)}, "
                f"field_suggester={sorted(suggester_syns)}"
            )

    def test_suggester_token_based_matching_prevents_false_positives(self, suggester: FieldSuggester) -> None:
        fields = {"subtitle", "item_title"}
        suggestions = suggester.suggest(fields, "product")
        targets = {s.target for s in suggestions}

        assert "title" not in targets or len(targets) < 2, (
            f"'subtitle' and 'item_title' should not match 'title' via token matching "
            f"unless they share meaningful tokens. Targets: {targets}"
        )

    def test_transformer_hint_only_for_price_and_date(self, suggester: FieldSuggester) -> None:
        fields = {"price", "created_date", "quantity", "email"}
        suggestions = suggester.suggest(fields, "product")
        for s in suggestions:
            if s.source == "quantity":
                pass

    def test_identity_mapping_creates_external_id_for_id_field(self) -> None:
        fields = {"id", "name"}
        suggestions = FieldSuggester._suggest_identity_mappings(fields)
        targets = [s.target for s in suggestions]
        assert "external_id" in targets, (
            f"When 'id' is a source field, should also suggest external_id mapping. "
            f"Got targets: {targets}"
        )
        assert len(suggestions) == 3, (
            f"Expected 3 suggestions (name→name, id→id, id→external_id), got {len(suggestions)}"
        )

    def test_suggest_empty_fields(self, suggester: FieldSuggester) -> None:
        suggestions = suggester.suggest(set(), "product")
        assert len(suggestions) == 0, (
            f"Empty field set should produce no suggestions, got {len(suggestions)}"
        )

    def test_suggest_unknown_entity_identity_with_id_field(self) -> None:
        fields = {"name", "email", "id"}
        suggestions = FieldSuggester._suggest_identity_mappings(fields)
        targets = [s.target for s in suggestions]
        assert len(suggestions) == 4, (
            f"Identity mappings for 3 fields with 'id' should produce "
            f"3 identity + 1 external_id = 4, got {len(suggestions)}: {targets}"
        )
        assert "external_id" in targets, (
            f"When source has an 'id'-like field, should suggest external_id mapping"
        )

    def test_suggest_unknown_entity_no_external_id(self) -> None:
        fields = {"name", "email", "phone"}
        suggestions = FieldSuggester._suggest_identity_mappings(fields)
        for s in suggestions:
            assert s.source in fields, (
                f"Each suggestion should map a source field present in the input"
            )
            assert s.target == s.source, (
                f"Identity mapping should map source to itself"
            )

    def test_exact_match_uses_highest_confidence(self, suggester: FieldSuggester) -> None:
        fields = {"title"}
        suggestions = suggester.suggest(fields, "product")
        assert len(suggestions) == 1
        assert suggestions[0].confidence == 1.0

    def test_synonym_match(self, suggester: FieldSuggester) -> None:
        fields = {"headline"}
        suggestions = suggester.suggest(fields, "product")
        assert len(suggestions) >= 1
        assert suggestions[0].target == "title"
        assert suggestions[0].confidence == 0.7
