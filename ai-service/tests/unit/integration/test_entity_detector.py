import pytest

from app.application.integration.discovery.entity_detector import EntityDetector


@pytest.fixture
def detector() -> EntityDetector:
    return EntityDetector()


class TestEntityDetector:
    def test_detect_product_by_fields(self, detector: EntityDetector) -> None:
        fields = {"title", "price", "sku", "description", "vendor"}
        result = detector.detect(fields)
        assert result.entity_type == "product"
        assert result.confidence > 0.0

    def test_detect_order_by_fields(self, detector: EntityDetector) -> None:
        fields = {"email", "total", "currency", "line_items", "financial_status"}
        result = detector.detect(fields)
        assert result.entity_type == "order"
        assert result.confidence > 0.0

    def test_detect_customer_by_fields(self, detector: EntityDetector) -> None:
        fields = {"email", "first_name", "last_name", "phone"}
        result = detector.detect(fields)
        assert result.entity_type == "customer"

    def test_detect_unknown_entity(self, detector: EntityDetector) -> None:
        fields = {"foo", "bar", "baz"}
        result = detector.detect(fields)
        assert result.entity_type is None
        assert result.confidence == 0.0

    def test_detect_with_hint(self, detector: EntityDetector) -> None:
        fields = {"title", "price", "sku"}
        result = detector.detect(fields, entity_type_hint="product")
        assert result.entity_type == "product"

    def test_detect_with_invalid_hint(self, detector: EntityDetector) -> None:
        fields = {"foo", "bar"}
        result = detector.detect(fields, entity_type_hint="invalid")
        assert result.entity_type is None

    def test_detect_exact_match_scoring(self, detector: EntityDetector) -> None:
        fields = {"title", "price"}
        # title, price are exact matches for product
        result = detector.detect(fields, entity_type_hint="product")
        assert result.entity_type == "product"
        assert result.confidence > 0

    def test_detect_synonym_matching(self, detector: EntityDetector) -> None:
        fields = {"stock", "cost", "body_html"}
        result = detector.detect(fields)
        assert result.entity_type is not None

    def test_detect_empty_fields(self, detector: EntityDetector) -> None:
        result = detector.detect(set())
        assert result.entity_type is None
        assert result.confidence == 0.0