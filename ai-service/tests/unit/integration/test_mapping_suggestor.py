import pytest

from app.application.integration.mapping.discovery import MappingSuggestor
from app.application.integration.discovery.field_suggester import FieldSuggester


@pytest.fixture
def suggestor() -> MappingSuggestor:
    return MappingSuggestor()


class TestMappingSuggestor:
    def test_suggest_product_mappings(self, suggestor: MappingSuggestor) -> None:
        fields = {"product_name", "price", "sku", "stock_level", "description", "tags"}
        mappings = suggestor.suggest_mappings(fields, "product")
        targets = {m.target for m in mappings}
        assert "title" in targets  # product_name → title (synonym)
        assert "price" in targets
        assert "sku" in targets
        assert "inventory_quantity" in targets  # stock → inventory_quantity

    def test_required_fields_set(self, suggestor: MappingSuggestor) -> None:
        fields = {"name", "price"}
        mappings = suggestor.suggest_mappings(fields, "product")
        for m in mappings:
            if m.target in ("title", "sku", "external_id"):
                assert m.required

    def test_min_confidence_filter(self, suggestor: MappingSuggestor) -> None:
        fields = {"obscure_field_xyz"}
        mappings = suggestor.suggest_mappings(fields, "product", min_confidence=0.9)
        assert len(mappings) == 0

    def test_no_duplicate_targets(self, suggestor: MappingSuggestor) -> None:
        fields = {"name", "product_name"}
        mappings = suggestor.suggest_mappings(fields, "product")
        targets = [m.target for m in mappings]
        assert targets.count("title") <= 1

    def test_order_mappings(self, suggestor: MappingSuggestor) -> None:
        fields = {"email", "total_price", "order_status", "currency_code"}
        mappings = suggestor.suggest_mappings(fields, "order")
        targets = {m.target for m in mappings}
        assert "email" in targets
        assert "total" in targets
        assert "currency" in targets

    def test_empty_fields(self, suggestor: MappingSuggestor) -> None:
        mappings = suggestor.suggest_mappings(set(), "product")
        assert len(mappings) == 0