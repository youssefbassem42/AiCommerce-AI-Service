import pytest

from app.application.integration.discovery.field_suggester import FieldSuggester


@pytest.fixture
def suggester() -> FieldSuggester:
    return FieldSuggester()


class TestFieldSuggester:
    def test_suggest_product_fields(self, suggester: FieldSuggester) -> None:
        fields = {"product_name", "price", "sku", "stock_level", "description"}
        suggestions = suggester.suggest(fields, "product")
        targets = {s.target for s in suggestions}
        assert "title" in targets  # product_name → title (synonym)
        assert "price" in targets
        assert "sku" in targets
        assert "inventory_quantity" in targets  # stock → inventory_quantity

    def test_suggest_confidence_scoring(self, suggester: FieldSuggester) -> None:
        fields = {"name"}
        suggestions = suggester.suggest(fields, "product")
        assert len(suggestions) >= 1
        for s in suggestions:
            assert 0.0 < s.confidence <= 1.0

    def test_exact_match_high_confidence(self, suggester: FieldSuggester) -> None:
        fields = {"sku"}
        suggestions = suggester.suggest(fields, "product")
        sku_suggestions = [s for s in suggestions if s.target == "sku"]
        assert len(sku_suggestions) == 1
        assert sku_suggestions[0].confidence == 1.0

    def test_synonym_match_medium_confidence(self, suggester: FieldSuggester) -> None:
        fields = {"upc"}
        suggestions = suggester.suggest(fields, "product")
        sku = [s for s in suggestions if s.target == "sku"]
        assert len(sku) >= 1
        # Strictly assert the synonym score: 0.7
        assert sku[0].confidence == 0.7

    def test_transformer_hint_for_price(self, suggester: FieldSuggester) -> None:
        fields = {"cost"}
        suggestions = suggester.suggest(fields, "product")
        price = [s for s in suggestions if s.target == "price"]
        if price:
            assert price[0].transformer == "string_to_decimal"

    def test_suggest_order_fields(self, suggester: FieldSuggester) -> None:
        fields = {"email", "total_price", "order_status"}
        suggestions = suggester.suggest(fields, "order")
        targets = {s.target for s in suggestions}
        assert "email" in targets
        assert "total" in targets

    def test_no_match(self, suggester: FieldSuggester) -> None:
        fields = {"completely_unrelated_field"}
        suggestions = suggester.suggest(fields, "product")
        assert len(suggestions) == 0