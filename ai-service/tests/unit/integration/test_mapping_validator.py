import pytest

from app.application.integration.mapping.validation import MappingValidator
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig


@pytest.fixture
def validator() -> MappingValidator:
    return MappingValidator()


class TestMappingValidator:
    def test_valid_product_mapping(self, validator: MappingValidator) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
            field_mappings=[
                FieldMapping(source="name", target="title", required=True),
                FieldMapping(source="price", target="price", transformer="string_to_decimal"),
                FieldMapping(source="sku", target="sku", required=True),
            ],
        )
        result = validator.validate(mapping, external_schema_fields={"name", "price", "sku"})
        assert result.valid

    def test_invalid_transformer(self, validator: MappingValidator) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
            field_mappings=[
                FieldMapping(source="name", target="title", transformer="nonexistent"),
            ],
        )
        result = validator.validate(mapping)
        assert not result.valid
        assert any("transformer" in i.message.lower() for i in result.issues if i.severity == "error")

    def test_missing_source_field_warning(self, validator: MappingValidator) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
            field_mappings=[
                FieldMapping(source="nonexistent", target="title"),
            ],
        )
        result = validator.validate(mapping, external_schema_fields={"name", "price"})
        assert any("nonexistent" in i.message for i in result.issues)

    def test_no_field_mappings_warning(self, validator: MappingValidator) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
        )
        result = validator.validate(mapping)
        assert any("field mappings" in i.message.lower() for i in result.issues)

    def test_unknown_entity_type(self, validator: MappingValidator) -> None:
        mapping = EntityMapping(
            entity_type="unknown_entity",
            list_path="/items",
            id_field="id",
            field_mappings=[
                FieldMapping(source="name", target="some_field"),
            ],
        )
        result = validator.validate(mapping)
        # Should still validate without canonical field check errors for unknown type
        assert result.valid is True