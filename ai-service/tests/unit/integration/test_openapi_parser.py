import pytest

from app.application.integration.openapi.parser import OpenApiParser
from app.domain.integration.exceptions import InvalidSpecException


@pytest.fixture
def parser() -> OpenApiParser:
    return OpenApiParser()


OPENAPI_V3_MINIMAL = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.example.com"}],
    "paths": {
        "/products": {
            "get": {
                "operationId": "listProducts",
                "summary": "List all products",
                "parameters": [
                    {"name": "page", "in": "query", "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {
                        "description": "A list of products",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ProductList"},
                            },
                        },
                    },
                },
            },
        },
        "/products/{id}": {
            "get": {
                "operationId": "getProduct",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {
                        "description": "A product",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Product"},
                            },
                        },
                    },
                },
            },
        },
    },
    "components": {
        "schemas": {
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "price": {"type": "number"},
                },
            },
            "ProductList": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Product"},
                    },
                },
            },
        },
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
        },
    },
}

SWAGGER_V2_MINIMAL = {
    "swagger": "2.0",
    "info": {"title": "Swagger Petstore", "version": "1.0.0"},
    "host": "petstore.example.com",
    "basePath": "/v2",
    "schemes": ["https"],
    "paths": {
        "/pet": {
            "post": {
                "operationId": "addPet",
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "schema": {"$ref": "#/definitions/Pet"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "successful operation",
                        "schema": {"$ref": "#/definitions/Pet"},
                    },
                },
            },
        },
    },
    "definitions": {
        "Pet": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
            },
        },
    },
    "securityDefinitions": {
        "api_key": {
            "type": "apiKey",
            "in": "header",
            "name": "api_key",
        },
    },
}


class TestOpenApiParserV3:
    def test_parse_v3_minimal(self, parser: OpenApiParser) -> None:
        result = parser.parse(OPENAPI_V3_MINIMAL, "shopify")
        assert result.platform_name == "shopify"
        assert result.base_url == "https://api.example.com"
        assert result.api_version == "3.0.0"
        assert len(result.endpoints) == 2
        assert result.endpoints[0].path == "/products"
        assert result.endpoints[0].method == "GET"

    def test_parse_v3_extracts_schemas(self, parser: OpenApiParser) -> None:
        result = parser.parse(OPENAPI_V3_MINIMAL, "shopify")
        assert "Product" in result.schemas
        assert "ProductList" in result.schemas

    def test_parse_v3_extracts_auth(self, parser: OpenApiParser) -> None:
        result = parser.parse(OPENAPI_V3_MINIMAL, "shopify")
        assert len(result.auth_methods) == 1
        auth = result.auth_methods[0]
        assert auth.name == "X-API-Key"
        assert auth.type.value == "apiKey"

    def test_parse_v3_missing_servers(self, parser: OpenApiParser) -> None:
        spec = dict(OPENAPI_V3_MINIMAL)
        del spec["servers"]
        result = parser.parse(spec, "shopify")
        assert result.base_url == ""

    def test_parse_v3_empty_paths(self, parser: OpenApiParser) -> None:
        spec = dict(OPENAPI_V3_MINIMAL)
        spec["paths"] = {}
        result = parser.parse(spec, "shopify")
        assert len(result.endpoints) == 0


class TestOpenApiParserV2:
    def test_parse_v2_minimal(self, parser: OpenApiParser) -> None:
        result = parser.parse(SWAGGER_V2_MINIMAL, "petstore")
        assert result.platform_name == "petstore"
        assert result.base_url == "https://petstore.example.com/v2"
        assert len(result.endpoints) == 1
        assert result.endpoints[0].path == "/pet"
        assert result.endpoints[0].method == "POST"

    def test_parse_v2_schemas(self, parser: OpenApiParser) -> None:
        result = parser.parse(SWAGGER_V2_MINIMAL, "petstore")
        assert "Pet" in result.schemas

    def test_parse_v2_security(self, parser: OpenApiParser) -> None:
        result = parser.parse(SWAGGER_V2_MINIMAL, "petstore")
        assert len(result.auth_methods) == 1


class TestOpenApiParserErrors:
    def test_not_a_dict(self, parser: OpenApiParser) -> None:
        with pytest.raises(InvalidSpecException):
            parser.parse("not a dict", "test")

    def test_missing_version_key(self, parser: OpenApiParser) -> None:
        with pytest.raises(InvalidSpecException):
            parser.parse({"info": {}}, "test")

    def test_malformed_paths(self, parser: OpenApiParser) -> None:
        spec = dict(OPENAPI_V3_MINIMAL)
        spec["paths"] = "invalid"
        result = parser.parse(spec, "test")
        assert len(result.endpoints) == 0