import json
import logging
from typing import Any, Optional

import yaml

from app.domain.integration.exceptions import InvalidSpecException
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation

logger = logging.getLogger(__name__)


class EndpointSchema:
    """Represents a single endpoint discovered from the spec."""

    def __init__(
        self,
        path: str,
        method: str,
        operation_id: Optional[str] = None,
        parameters: Optional[list[dict]] = None,
        response_schema_ref: Optional[str] = None,
        summary: Optional[str] = None,
    ):
        self.path = path
        self.method = method.upper()
        self.operation_id = operation_id
        self.parameters = parameters or []
        self.response_schema_ref = response_schema_ref
        self.summary = summary


class IntegrationSchema:
    """Complete parsed representation of an OpenAPI spec."""

    def __init__(
        self,
        platform_name: str,
        base_url: str,
        api_version: str,
        endpoints: list[EndpointSchema],
        schemas: dict[str, dict],
        auth_methods: list[AuthConfig],
        pagination_info: Optional[dict] = None,
    ):
        self.platform_name = platform_name
        self.base_url = base_url
        self.api_version = api_version
        self.endpoints = endpoints
        self.schemas = schemas
        self.auth_methods = auth_methods
        self.pagination_info = pagination_info or {}


class OpenApiParser:
    """Parses an OpenAPI/Swagger spec dictionary into a canonical IntegrationSchema."""

    @staticmethod
    def normalize_spec(spec: Any) -> dict:
        if isinstance(spec, dict):
            return spec
        if isinstance(spec, str):
            try:
                parsed = json.loads(spec)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            try:
                parsed = yaml.safe_load(spec)
                if isinstance(parsed, dict):
                    return parsed
            except yaml.YAMLError:
                pass
        raise InvalidSpecException(
            "Spec must be a valid OpenAPI/Swagger specification in JSON or YAML format."
        )

    def parse(self, spec: Any, platform_name: str) -> IntegrationSchema:
        raw = self.normalize_spec(spec)

        if raw.get("openapi"):
            return self._parse_v3(raw, platform_name)
        if raw.get("swagger"):
            return self._parse_v2(raw, platform_name)

        raise InvalidSpecException(
            "Spec must contain 'openapi' (v3) or 'swagger' (v2) key."
        )

    def _parse_v3(self, spec: dict, platform_name: str) -> IntegrationSchema:
        base_url = self._extract_base_url_v3(spec)
        api_version = spec.get("openapi", "3.0.0")
        endpoints = self._extract_paths(spec.get("paths", {}), spec)
        endpoints.extend(self._extract_webhooks(spec))
        schemas = self._extract_components_schemas_v3(spec)
        auth_methods = self._extract_security_schemes_v3(spec)
        return IntegrationSchema(
            platform_name=platform_name,
            base_url=base_url,
            api_version=api_version,
            endpoints=endpoints,
            schemas=schemas,
            auth_methods=auth_methods,
        )

    def _parse_v2(self, spec: dict, platform_name: str) -> IntegrationSchema:
        base_url = self._extract_base_url_v2(spec)
        api_version = spec.get("info", {}).get("version", "2.0")
        endpoints = self._extract_paths(spec.get("paths", {}), spec)
        schemas = spec.get("definitions", {})
        auth_methods = self._extract_security_definitions_v2(spec)
        return IntegrationSchema(
            platform_name=platform_name,
            base_url=base_url,
            api_version=api_version,
            endpoints=endpoints,
            schemas=schemas,
            auth_methods=auth_methods,
        )

    def _extract_base_url_v3(self, spec: dict) -> str:
        servers = spec.get("servers")
        if servers and isinstance(servers, list) and len(servers) > 0:
            url = servers[0].get("url", "")
            if url:
                return url.rstrip("/")
        description = spec.get("info", {}).get("description", "") or ""
        logger.warning("No server URL found in spec v3; fallback to empty. spec: %s", description[:80])
        return ""

    def _extract_base_url_v2(self, spec: dict) -> str:
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        scheme = "https"
        schemes = spec.get("schemes", [])
        if schemes and isinstance(schemes, list):
            scheme = schemes[0]
        if host:
            return f"{scheme}://{host}{base_path}".rstrip("/")
        logger.warning("No host found in Swagger spec.")
        return ""

    def _extract_paths(
        self, paths: dict, spec: dict
    ) -> list[EndpointSchema]:
        result: list[EndpointSchema] = []
        if not isinstance(paths, dict):
            logger.warning("'paths' is not a dict, got %s", type(paths).__name__)
            return result
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            path_params = methods.get("parameters", []) if isinstance(methods, dict) else []
            for method, details in methods.items():
                if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                    continue
                operation_params = details.get("parameters", [])
                all_params = path_params + operation_params
                response_schema_ref = self._extract_response_schema_ref(details)
                result.append(
                    EndpointSchema(
                        path=path,
                        method=method,
                        operation_id=details.get("operationId"),
                        parameters=all_params,
                        response_schema_ref=response_schema_ref,
                        summary=details.get("summary"),
                    )
                )
        return result

    def _extract_webhooks(self, spec: dict) -> list[EndpointSchema]:
        result: list[EndpointSchema] = []
        webhooks = spec.get("webhooks", {})
        if not isinstance(webhooks, dict):
            return result
        for name, webhook in webhooks.items():
            if not isinstance(webhook, dict):
                continue
            for method, details in webhook.items():
                if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                    continue
                parameters = details.get("parameters", [])
                response_schema_ref = self._extract_response_schema_ref(details)
                result.append(
                    EndpointSchema(
                        path=f"/webhooks/{name}",
                        method=method,
                        operation_id=details.get("operationId"),
                        parameters=parameters,
                        response_schema_ref=response_schema_ref,
                        summary=details.get("summary"),
                    )
                )
        return result

    def _extract_response_schema_ref(self, operation: dict) -> Optional[str]:
        responses = operation.get("responses", {})
        if not isinstance(responses, dict):
            return None
        for status_code in ("200", "201", "default"):
            response = responses.get(status_code)
            if not isinstance(response, dict):
                continue
            content = response.get("content") if "content" in response else response
            if isinstance(content, dict):
                if "$ref" in content:
                    return content["$ref"]
                for _, media_type in content.items():
                    if isinstance(media_type, dict):
                        schema = media_type.get("schema", {})
                        if "$ref" in schema:
                            return schema["$ref"]
                        if "items" in schema and isinstance(schema["items"], dict) and "$ref" in schema["items"]:
                            return schema["items"]["$ref"]
            schema = response.get("schema", {})
            if "$ref" in schema:
                return schema["$ref"]
            if "items" in schema and isinstance(schema["items"], dict) and "$ref" in schema["items"]:
                return schema["items"]["$ref"]
        return None

    def _extract_components_schemas_v3(self, spec: dict) -> dict[str, dict]:
        components = spec.get("components", {})
        if not isinstance(components, dict):
            return {}
        schemas = components.get("schemas", {})
        return schemas if isinstance(schemas, dict) else {}

    def _extract_security_schemes_v3(self, spec: dict) -> list[AuthConfig]:
        components = spec.get("components", {})
        if not isinstance(components, dict):
            return []
        schemes = components.get("securitySchemes", {})
        return self._parse_security_schemes(schemes) if isinstance(schemes, dict) else []

    def _extract_security_definitions_v2(self, spec: dict) -> list[AuthConfig]:
        definitions = spec.get("securityDefinitions", {})
        return self._parse_security_schemes(definitions) if isinstance(definitions, dict) else []

    def _parse_security_schemes(self, raw: dict) -> list[AuthConfig]:
        result: list[AuthConfig] = []
        for name, scheme in raw.items():
            if not isinstance(scheme, dict):
                continue
            try:
                auth_type_str = scheme.get("type", "")
                auth_type = AuthType(auth_type_str) if auth_type_str in AuthType._value2member_map_ else None
                if auth_type is None:
                    logger.warning("Unsupported auth type '%s' in scheme '%s'", auth_type_str, name)
                    continue
                if auth_type == AuthType.APIKEY:
                    in_ = scheme.get("in", "header")
                    result.append(
                        AuthConfig(
                            type=AuthType.APIKEY,
                            credentials_location=CredentialsLocation(in_)
                            if in_ in CredentialsLocation._value2member_map_
                            else CredentialsLocation.HEADER,
                            name=scheme.get("name", name),
                        )
                    )
                elif auth_type in (AuthType.BEARER, AuthType.BASIC):
                    result.append(
                        AuthConfig(
                            type=auth_type,
                            scheme=scheme.get("scheme", auth_type.value),
                        )
                    )
                elif auth_type == AuthType.OAUTH2:
                    flows = scheme.get("flows", {})
                    first_flow_name = next(iter(flows.keys()), "clientCredentials")
                    first_flow = flows.get(first_flow_name, {})
                    result.append(
                        AuthConfig(
                            type=AuthType.OAUTH2,
                            token_url=first_flow.get("tokenUrl", ""),
                            flow=first_flow_name,
                        )
                    )
            except Exception as e:
                logger.warning("Failed to parse security scheme '%s': %s", name, e)
        return result