import pytest

from app.application.integration.discovery.entity_detector import (
    CANONICAL_FIELDS,
    EntityDetector,
)


@pytest.fixture
def detector() -> EntityDetector:
    return EntityDetector()


class TestEntityDetectorBugs:
    def test_non_commerce_fields_not_matched(self, detector: EntityDetector) -> None:
        fields = {"subtitle", "diagnosis_code"}
        result = detector.detect(fields)
        assert result.entity_type is None, (
            f"Non-commerce fields should return None. "
            f"Got entity_type='{result.entity_type}' confidence={result.confidence}"
        )

    def test_commerce_field_with_id_suffix_still_matches(self, detector: EntityDetector) -> None:
        fields = {"some_random_id_field_xyz"}
        result = detector.detect(fields)
        if result.entity_type is not None:
            assert result.confidence < 0.5, (
                f"Non-commerce field 'some_random_id_field_xyz' should have low confidence "
                f"if it matches at all. Got {result.confidence}"
            )

    def test_identifier_field_no_false_product(self, detector: EntityDetector) -> None:
        fields = {"identifier", "identification_number", "description_of_work"}
        result = detector.detect(fields)
        if result.entity_type is not None:
            assert result.confidence < 0.4, (
                f"Non-commerce fields should not confidently detect as any entity. "
                f"Got {result.entity_type} confidence={result.confidence}"
            )

    def test_inventory_is_supported(self, detector: EntityDetector) -> None:
        assert "inventory" in CANONICAL_FIELDS, (
            f"inventory entity type must be in CANONICAL_FIELDS. Available types: {list(CANONICAL_FIELDS.keys())}"
        )

    def test_inventory_detected_with_stock_fields(self, detector: EntityDetector) -> None:
        fields = {"product_id", "variant_id", "quantity", "available"}
        result = detector.detect(fields)
        assert result.entity_type == "inventory", f"Expected 'inventory' for stock fields, got '{result.entity_type}'"

    def test_confidence_bounded(self, detector: EntityDetector) -> None:
        fields = {
            "title",
            "price",
            "sku",
            "description",
            "vendor",
            "product_type",
            "tags",
            "status",
            "weight",
            "handle",
        }
        result = detector.detect(fields, entity_type_hint="product")
        assert result.confidence <= 1.0, f"Confidence should be bounded by 1.0, got {result.confidence}"

    def test_synonyms_unified_with_field_suggester(self, detector: EntityDetector) -> None:
        from app.application.integration.discovery.entity_detector import FIELD_SYNONYMS
        from app.application.integration.discovery.field_suggester import SYNONYM_MAP

        for canon_field, entity_syns in FIELD_SYNONYMS.items():
            assert canon_field in SYNONYM_MAP, f"Canonical field '{canon_field}' missing from suggester SYNONYM_MAP"
            suggester_syns = set(SYNONYM_MAP[canon_field])
            assert entity_syns == suggester_syns, (
                f"Synonym mismatch for '{canon_field}': "
                f"entity_detector={sorted(entity_syns)} vs "
                f"field_suggester={sorted(suggester_syns)}"
            )

    def test_empty_set_returns_none(self, detector: EntityDetector) -> None:
        result = detector.detect(set())
        assert result.entity_type is None
        assert result.confidence == 0.0

    def test_non_commerce_fields_return_low_confidence(self, detector: EntityDetector) -> None:
        fields = {"patient_name", "diagnosis_code", "appointment_date", "doctor_name", "clinic_id"}
        result = detector.detect(fields)
        if result.entity_type is not None:
            assert result.confidence < 0.5, (
                f"Medical fields '{fields}' detected as '{result.entity_type}' "
                f"with confidence {result.confidence}. Should be low."
            )

    def test_category_detected_with_minimal_fields(self, detector: EntityDetector) -> None:
        fields = {"name", "description", "parent_id", "image", "sort_order"}
        result = detector.detect(fields)
        assert result.entity_type == "category", f"Expected 'category' for category fields, got '{result.entity_type}'"

    def test_exact_match_field(self, detector: EntityDetector) -> None:
        fields = {"title", "price"}
        result = detector.detect(fields, entity_type_hint="product")
        assert result.entity_type == "product"
        assert result.confidence > 0
