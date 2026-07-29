import pytest

from app.application.integration.openapi.resolver import RefResolver, ResolvedField


class TestRefResolver:
    def test_resolve_simple_schema(self) -> None:
        schemas = {
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "price": {"type": "number"},
                },
                "required": ["id", "title"],
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Product"})
        assert len(result.fields) == 3
        field_names = {f.name for f in result.fields}
        assert field_names == {"id", "title", "price"}
        id_field = next(f for f in result.fields if f.name == "id")
        assert id_field.required is True
        assert id_field.field_type == "string"

    def test_resolve_all_of_merge(self) -> None:
        schemas = {
            "Base": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
            "Extended": {
                "allOf": [
                    {"$ref": "#/components/schemas/Base"},
                    {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "required": ["name"],
                    },
                ],
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Extended"})
        assert len(result.fields) == 2
        field_names = {f.name for f in result.fields}
        assert field_names == {"id", "name"}

    def test_one_of_picks_first(self) -> None:
        schemas = {
            "Variant": {
                "oneOf": [
                    {"type": "object", "properties": {"sku": {"type": "string"}}},
                    {"type": "object", "properties": {"barcode": {"type": "string"}}},
                ],
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Variant"})
        assert len(result.fields) == 1
        assert result.fields[0].name == "sku"

    def test_any_of_picks_first(self) -> None:
        schemas = {
            "Price": {
                "anyOf": [
                    {"type": "object", "properties": {"amount": {"type": "number"}}},
                    {"type": "object", "properties": {"price": {"type": "number"}}},
                ],
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Price"})
        assert len(result.fields) == 1
        assert result.fields[0].name == "amount"

    def test_circular_ref_detection(self) -> None:
        schemas = {
            "Node": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "child": {"$ref": "#/components/schemas/Node"},
                },
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Node"})
        assert result.resolved_name == "Node"
        assert len(result.fields) == 2

    def test_nonexistent_ref(self) -> None:
        schemas: dict = {}
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Missing"})
        assert len(result.fields) == 0

    def test_max_depth_guard(self) -> None:
        schemas = {
            "Deep": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
            },
        }
        resolver = RefResolver(schemas)
        resolver.MAX_DEPTH = 0
        result = resolver.resolve({"$ref": "#/components/schemas/Deep"})
        assert len(result.fields) == 0

    def test_swagger_ref_format(self) -> None:
        schemas = {
            "Product": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/definitions/Product"})
        assert len(result.fields) == 1

    def test_nested_properties(self) -> None:
        schemas = {
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                },
            },
            "Customer": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"$ref": "#/components/schemas/Address"},
                },
            },
        }
        resolver = RefResolver(schemas)
        result = resolver.resolve({"$ref": "#/components/schemas/Customer"})
        assert len(result.fields) == 3
        names = {f.name for f in result.fields}
        assert names == {"name", "street", "city"}

    def test_empty_schemas(self) -> None:
        resolver = RefResolver({})
        result = resolver.resolve({})
        assert len(result.fields) == 0

    def test_no_properties(self) -> None:
        resolver = RefResolver({})
        result = resolver.resolve({"type": "object"})
        assert len(result.fields) == 0