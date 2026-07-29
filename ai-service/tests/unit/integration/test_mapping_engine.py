from decimal import Decimal

import pytest

from app.application.integration.mapping.engine import MappingEngine
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping


@pytest.fixture
def engine() -> MappingEngine:
    return MappingEngine()


@pytest.fixture
def product_mapping() -> EntityMapping:
    return EntityMapping(
        entity_type="product",
        list_path="/products",
        id_field="id",
        field_mappings=[
            FieldMapping(source="name", target="title", required=True),
            FieldMapping(source="price", target="price", transformer="string_to_decimal"),
            FieldMapping(source="sku", target="sku", required=True),
            FieldMapping(source="stock_count", target="inventory_quantity", default_value=0),
            FieldMapping(source="description", target="description"),
            FieldMapping(source="tags", target="tags", transformer="split_by_comma"),
        ],
    )


class TestMappingEngine:
    def test_apply_valid_item(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {
            "name": "Test Product",
            "price": "29.99",
            "sku": "SKU-001",
            "stock_count": 100,
            "description": "A great product",
            "tags": "new,featured",
        }
        result = engine.apply(item, product_mapping)
        assert result.entity_type == "product"
        assert result.data["title"] == "Test Product"
        assert result.data["sku"] == "SKU-001"
        assert result.data["description"] == "A great product"
        assert isinstance(result.data["price"], Decimal)
        assert float(result.data["price"]) == 29.99
        assert result.data["inventory_quantity"] == 100
        assert result.data["tags"] == ["new", "featured"]
        assert result.report.success

    def test_apply_missing_required_field(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {"name": "Test Product"}
        result = engine.apply(item, product_mapping)
        assert result.report.errors
        assert any("Required source field 'sku'" in e for e in result.report.errors)

    def test_apply_default_value(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {"name": "Test", "price": "10.00", "sku": "S1"}
        result = engine.apply(item, product_mapping)
        assert result.data["inventory_quantity"] == 0

    def test_dot_notation_access(self, engine: MappingEngine) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
            field_mappings=[
                FieldMapping(source="shipping.city", target="city"),
                FieldMapping(source="shipping.zip", target="zip"),
            ],
        )
        item = {"shipping": {"city": "Portland", "zip": "97201"}}
        result = engine.apply(item, mapping)
        assert result.data["city"] == "Portland"
        assert result.data["zip"] == "97201"

    def test_missing_dot_notation_field(self, engine: MappingEngine) -> None:
        mapping = EntityMapping(
            entity_type="product",
            list_path="/products",
            id_field="id",
            field_mappings=[
                FieldMapping(source="nonexistent.field", target="test"),
            ],
        )
        item = {}
        result = engine.apply(item, mapping)
        assert "test" not in result.data or result.data.get("test") is None

    def test_transformer_failure(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {"name": "Test", "price": "not_a_number", "sku": "S1"}
        result = engine.apply(item, product_mapping)
        # Transformer failure shouldn't stop the mapping
        assert "price" in result.data
        assert not result.report.errors

    def test_null_value_with_default(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {"name": "Test", "price": "10.00", "sku": "S1", "stock_count": None}
        result = engine.apply(item, product_mapping)
        assert result.data["inventory_quantity"] == 0  # default_value used

    def test_empty_field_mappings(self, engine: MappingEngine) -> None:
        mapping = EntityMapping(entity_type="product", list_path="/products", id_field="id")
        item = {"name": "Test"}
        result = engine.apply(item, mapping)
        assert result.data == {"name": "Test"}
        assert result.report.warnings

    def test_all_field_types(self, engine: MappingEngine, product_mapping: EntityMapping) -> None:
        item = {
            "name": "Test",
            "price": "19.99",
            "sku": "S1",
            "stock_count": 50,
            "description": "desc",
            "tags": "a,b",
        }
        result = engine.apply(item, product_mapping)
        assert len(result.report.fields) == 6
        assert result.report.mapped_count >= 5
