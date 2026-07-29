import pytest

from app.application.integration.discovery.endpoint_classifier import EndpointClassifier
from app.application.integration.openapi.parser import OpenApiParser
from app.application.integration.openapi.validator import SpecValidator


@pytest.fixture
def parser() -> OpenApiParser:
    return OpenApiParser()


@pytest.fixture
def validator() -> SpecValidator:
    return SpecValidator()


@pytest.fixture
def classifier() -> EndpointClassifier:
    return EndpointClassifier()


class TestOpenApiParserBugs:
    def test_parse_v2_spec(self, parser: OpenApiParser) -> None:
        v2_spec = {
            "swagger": "2.0",
            "info": {"title": "Test API", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "schemes": ["https"],
            "paths": {
                "/products": {
                    "get": {
                        "operationId": "listProducts",
                        "responses": {
                            "200": {
                                "description": "OK",
                                "schema": {"$ref": "#/definitions/Product"},
                            }
                        },
                    }
                }
            },
            "definitions": {
                "Product": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                    },
                }
            },
        }
        result = parser.parse(v2_spec, "test_platform")

        assert len(result.endpoints) > 0, "v2 spec should produce endpoints"
        assert result.base_url == "https://api.example.com/v1", (
            f"v2 base URL should be https://api.example.com/v1 but got '{result.base_url}'"
        )

    def test_path_level_parameters_merged(self, parser: OpenApiParser) -> None:
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/products/{id}": {
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "get": {
                        "operationId": "getProduct",
                        "parameters": [
                            {
                                "name": "include",
                                "in": "query",
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "OK",
                                "content": {"application/json": {"schema": {"type": "object"}}},
                            }
                        },
                    },
                }
            },
        }
        result = parser.parse(spec, "test")
        for ep in result.endpoints:
            if ep.path == "/products/{id}":
                param_names = [p.get("name") for p in ep.parameters]
                assert "id" in param_names, (
                    f"Path-level parameter 'id' should be merged into endpoint. Got params: {param_names}"
                )
                assert "include" in param_names, (
                    f"Operation-level parameter 'include' should be preserved. Got params: {param_names}"
                )

    def test_webhooks_extracted(self, parser: OpenApiParser) -> None:
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0"},
            "webhooks": {
                "newOrder": {
                    "post": {
                        "operationId": "newOrderWebhook",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
            "paths": {},
        }
        result = parser.parse(spec, "test")
        webhook_endpoints = [ep for ep in result.endpoints if ep.operation_id == "newOrderWebhook"]
        assert len(webhook_endpoints) == 1, (
            f"Webhooks section should produce endpoints. "
            f"Got {len(webhook_endpoints)} webhook endpoints. "
            f"Total endpoints: {len(result.endpoints)}"
        )

    def test_min_endpoints_not_present_on_parser(self, parser: OpenApiParser) -> None:
        assert not hasattr(parser, "MIN_ENDPOINTS"), "MIN_ENDPOINTS should not exist on parser (removed dead code)"

    def test_v2_base_url_extraction(self, parser: OpenApiParser) -> None:
        spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0"},
            "host": "api.example.com:8080",
            "basePath": "/api/v2",
            "schemes": ["http"],
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "listUsers",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        result = parser.parse(spec, "test")
        assert result.base_url == "http://api.example.com:8080/api/v2", (
            f"Base URL should be http://api.example.com:8080/api/v2 but got '{result.base_url}'"
        )

    def test_v2_with_no_schemes_defaults_to_https(self, parser: OpenApiParser) -> None:
        spec = {
            "swagger": "2.0",
            "info": {"title": "Test", "version": "1.0"},
            "host": "api.example.com",
            "basePath": "/v1",
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        result = parser.parse(spec, "test")
        assert result.base_url.startswith("https://"), (
            f"v2 spec without schemes should default to https. Got: '{result.base_url}'"
        )


class TestSpecValidatorBugs:
    def test_zero_endpoints_does_not_crash(self, validator: SpecValidator) -> None:
        from app.application.integration.openapi.parser import IntegrationSchema

        schema = IntegrationSchema(
            platform_name="test",
            base_url="http://example.com",
            api_version="1.0",
            endpoints=[],
            schemas={},
            auth_methods=[],
        )
        validator.validate(schema)

    def test_dangling_ref_not_detected(self, validator: SpecValidator) -> None:
        from app.application.integration.openapi.parser import EndpointSchema, IntegrationSchema

        schema = IntegrationSchema(
            platform_name="test",
            base_url="http://example.com",
            api_version="1.0",
            endpoints=[
                EndpointSchema(
                    path="/products",
                    method="GET",
                    operation_id="listProducts",
                    response_schema_ref="#/components/schemas/NonExistentSchema",
                )
            ],
            schemas={},
            auth_methods=[],
            pagination_info={},
        )
        report = validator.validate(schema)
        [e for e in report.errors if "NonExistentSchema" in e or "ref" in e.lower()]

    def test_empty_paths_returns_empty(self, parser: OpenApiParser) -> None:
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {},
        }
        result = parser.parse(spec, "test")
        assert len(result.endpoints) == 0


class TestEndpointClassifierBugs:
    def test_classify_with_minimal_path(self, classifier: EndpointClassifier) -> None:
        from app.application.integration.openapi.parser import EndpointSchema

        ep = EndpointSchema(
            path="/products",
            method="GET",
            operation_id="listProducts",
            summary="List products",
        )
        result = classifier.classify(ep)
        assert result is not None
        assert result.operation == "list"

    def test_classify_detail_operation(self, classifier: EndpointClassifier) -> None:
        from app.application.integration.openapi.parser import EndpointSchema

        ep = EndpointSchema(
            path="/products/{id}",
            method="GET",
            operation_id="getProduct",
        )
        result = classifier.classify(ep)
        assert result is not None
        assert result.operation == "detail"
