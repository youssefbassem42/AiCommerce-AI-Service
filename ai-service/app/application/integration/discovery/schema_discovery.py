import logging
from typing import Any, Optional

from app.application.integration.discovery.endpoint_classifier import EndpointClassifier
from app.application.integration.openapi.parser import EndpointSchema
from app.application.integration.openapi.resolver import RefResolver, ResolvedField, ResolvedSchema

logger = logging.getLogger(__name__)


class DiscoveredSchema:
    """A resolved schema associated with an endpoint."""

    def __init__(
        self,
        endpoint: EndpointSchema,
        status_code: str,
        content_type: str,
        resolved: ResolvedSchema,
    ):
        self.endpoint = endpoint
        self.status_code = status_code
        self.content_type = content_type
        self.resolved = resolved
        self.resolved_name = resolved.resolved_name

    @property
    def field_names(self) -> set[str]:
        return {f.name for f in self.resolved.fields}

    @property
    def field_list(self) -> list[ResolvedField]:
        return self.resolved.fields


class SchemaDiscovery:
    """Discovers response schemas for each endpoint by resolving $ref references."""

    def __init__(self, resolver: RefResolver):
        self._resolver = resolver

    def discover(
        self, endpoints: list[EndpointSchema]
    ) -> list[DiscoveredSchema]:
        result: list[DiscoveredSchema] = []
        for ep in endpoints:
            discovered = self._discover_for_endpoint(ep)
            if discovered:
                result.append(discovered)
        return result

    def _discover_for_endpoint(
        self, endpoint: EndpointSchema
    ) -> Optional[DiscoveredSchema]:
        if not endpoint.response_schema_ref:
            return None

        status_code, content_type = self._best_response_info(endpoint)
        resolved = self._resolve_schema_ref(endpoint.response_schema_ref)
        if resolved is None:
            return None

        return DiscoveredSchema(
            endpoint=endpoint,
            status_code=status_code,
            content_type=content_type,
            resolved=resolved,
        )

    def _resolve_schema_ref(self, ref: str) -> Optional[ResolvedSchema]:
        schema_stub: dict[str, Any] = {"$ref": ref}
        resolved = self._resolver.resolve(schema_stub)
        if not resolved.fields and not resolved.raw_schema.get("properties"):
            logger.debug("Schema ref '%s' resolved to empty field set.", ref)
        return resolved

    @staticmethod
    def _best_response_info(endpoint: EndpointSchema) -> tuple[str, str]:
        return "200", "application/json"

    def build_field_map(
        self, discovered: list[DiscoveredSchema]
    ) -> dict[str, set[str]]:
        field_map: dict[str, set[str]] = {}
        for ds in discovered:
            fields = ds.field_names
            key = ds.endpoint.path
            if key in field_map:
                field_map[key].update(fields)
            else:
                field_map[key] = set(fields)
        return field_map