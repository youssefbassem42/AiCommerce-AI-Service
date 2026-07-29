import pytest

from app.application.integration.openapi.parser import IntegrationSchema, EndpointSchema, OpenApiParser
from app.application.integration.openapi.validator import SpecValidator
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType


@pytest.fixture
def validator() -> SpecValidator:
    return SpecValidator()


class TestSpecValidator:
    def test_valid_schema(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="shopify",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[
                EndpointSchema(path="/products", method="GET"),
                EndpointSchema(path="/products/{id}", method="GET"),
            ],
            schemas={"Product": {"type": "object"}},
            auth_methods=[AuthConfig(type=AuthType.APIKEY, name="X-Key")],
        )
        report = validator.validate(schema)
        assert not report.has_errors
        assert not report.has_warnings

    def test_no_endpoints_error(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[],
            schemas={},
            auth_methods=[],
        )
        report = validator.validate(schema)
        assert report.has_errors
        assert any("zero endpoints" in e.lower() for e in report.errors)

    def test_no_auth_warning(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[EndpointSchema(path="/products", method="GET")],
            schemas={},
            auth_methods=[],
        )
        report = validator.validate(schema)
        assert any("authentication" in w.lower() for w in report.warnings)

    def test_no_base_url_error(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="",
            api_version="3.0.0",
            endpoints=[EndpointSchema(path="/products", method="GET")],
            schemas={},
            auth_methods=[],
        )
        report = validator.validate(schema)
        assert any("base url" in e.lower() for e in report.errors)

    def test_no_schemas_warning(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[EndpointSchema(path="/products", method="GET")],
            schemas={},
            auth_methods=[AuthConfig(type=AuthType.APIKEY, name="X-Key")],
        )
        report = validator.validate(schema)
        assert any("schemas" in w.lower() for w in report.warnings)

    def test_no_list_endpoint_warning(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[EndpointSchema(path="/products/{id}", method="GET")],
            schemas={},
            auth_methods=[],
        )
        report = validator.validate(schema)
        assert any("list" in w.lower() for w in report.warnings)

    def test_endpoint_path_format_warning(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[EndpointSchema(path="products", method="GET")],
            schemas={},
            auth_methods=[],
        )
        report = validator.validate(schema)
        assert any("should start with '/'" in w for w in report.warnings)

    def test_no_warnings_for_complete_spec(self, validator: SpecValidator) -> None:
        schema = IntegrationSchema(
            platform_name="test",
            base_url="https://api.example.com",
            api_version="3.0.0",
            endpoints=[
                EndpointSchema(path="/products", method="GET"),
                EndpointSchema(path="/products/{id}", method="GET"),
            ],
            schemas={"Product": {}},
            auth_methods=[AuthConfig(type=AuthType.APIKEY, name="Key")],
        )
        report = validator.validate(schema)
        assert not report.has_warnings
        assert not report.has_errors