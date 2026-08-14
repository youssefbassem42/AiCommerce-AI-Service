"""Real promotion integration (Fix 5.5).

Flow:

    Bundle Engine
        ↓
    PromoCodeService
        ↓
    e-commerce platform (coupon endpoint)
        ↓
    real coupon → coupon code

The Mongo "fake coupon" is gone. A promo code is only ever returned when the
store's connected e-commerce platform actually created a coupon. When the
platform cannot create one (no coupon-capable connection, no coupon create
endpoint, or the API call fails) the service returns ``None`` and the caller
shows NO promo code to the customer.
"""

import logging
from typing import Any
from uuid import uuid4

from app.application.integration.discovery.endpoint_classifier import EndpointClassifier
from app.application.integration.openapi.parser import EndpointSchema
from app.core.ai_logging import log_flow_event
from app.core.ai_settings import ai_settings
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.infrastructure.http.auth.auth_handler import AuthHandler
from app.infrastructure.http.clients.base_client import ConnectionConfig, ExternalApiClient
from app.infrastructure.http.ssrf import assert_safe_http_url
from app.infrastructure.mongodb.repositories.integration_connection_repository import (
    IntegrationConnectionMongoRepository,
)
from app.infrastructure.security.key_manager import KeyManager

logger = logging.getLogger(__name__)

PROMO_CODE_PREFIX = "BUNDLE"

COUPON_ENTITY_TYPES = {"coupon", "discount", "promotion"}

# Platform coupon schemas use different field names; each canonical field maps
# onto the accepted aliases, in preference order.
_CODE_FIELD_ALIASES = ("code", "coupon_code", "promo_code", "name")
_PERCENTAGE_FIELD_ALIASES = ("percentage", "percent", "discount_percentage", "discount_pct", "value")
_PRODUCT_SCOPE_ALIASES = ("product_ids", "applies_to_ids", "applies_to", "variant_ids")


class PromoCodeService:
    def __init__(
        self,
        connection_repo: IntegrationConnectionMongoRepository | None = None,
        key_manager: KeyManager | None = None,
        auth_handler: AuthHandler | None = None,
    ):
        self._connection_repo = connection_repo or IntegrationConnectionMongoRepository()
        self._key_manager = key_manager or KeyManager()
        self._auth_handler = auth_handler or AuthHandler()
        self._classifier = EndpointClassifier()

    async def generate_code(
        self,
        store_id: str,
        product_ids: list[str],
        discount_pct: float,
        bundle_id: str | None = None,
        prefix: str | None = None,
    ) -> str | None:
        """Create a real coupon on the store's e-commerce platform.

        Returns the platform coupon code, or ``None`` when the platform cannot
        create a coupon (never a fabricated code).
        """
        if not ai_settings.PROMO_CODES_ENABLED:
            log_flow_event(
                "promo.disabled",
                store_id=store_id,
                product_ids=product_ids,
                discount_pct=discount_pct,
                bundle_id=bundle_id,
                reason="promo_codes_enabled is false",
            )
            logger.info(
                "Promo code generation disabled by configuration (PROMO_CODES_ENABLED=false, store=%s)",
                store_id,
            )
            return None

        connection = await self._find_coupon_connection(store_id)
        if connection is None:
            log_flow_event(
                "promo.platform_unavailable",
                store_id=store_id,
                reason="no coupon-capable platform connection",
            )
            logger.info(
                "No coupon-capable platform connection for store %s; no promo code shown.",
                store_id,
            )
            return None

        endpoint = self._find_coupon_create_endpoint(connection)
        if endpoint is None:
            log_flow_event(
                "promo.platform_unavailable",
                store_id=store_id,
                reason="platform has no coupon create endpoint",
            )
            logger.info(
                "Platform connection for store %s has no coupon create endpoint; no promo code shown.",
                store_id,
            )
            return None

        code = f"{(prefix or PROMO_CODE_PREFIX)}-{uuid4().hex[:8].upper()}"
        payload = self._build_coupon_payload(connection, endpoint, code, product_ids, discount_pct)
        if "code" not in payload:
            log_flow_event(
                "promo.platform_error",
                store_id=store_id,
                error="coupon schema has no code field",
            )
            logger.warning("Coupon schema for store %s has no code field; no promo code shown.", store_id)
            return None

        try:
            client = self._build_client(connection)
            try:
                response = await client.post(endpoint["path"], body=payload)
            finally:
                await client.close()
        except Exception as exc:
            logger.error("Coupon creation failed for store %s: %s", store_id, exc, exc_info=True)
            log_flow_event(
                "promo.platform_error",
                store_id=store_id,
                error=str(exc),
            )
            return None

        created_code = self._extract_coupon_code(response) or code
        log_flow_event(
            "promo.created",
            store_id=store_id,
            code=created_code,
            discount_pct=discount_pct,
            bundle_id=bundle_id,
            product_ids=product_ids,
        )
        logger.info("Created real coupon %s for store %s", created_code, store_id)
        return created_code

    async def redeem_code(self, code: str, store_id: str) -> bool:
        """Record a promo code being applied.

        The actual redemption happens at the platform checkout — the coupon is
        real. This hook only records the ``promo_applied`` analytics event.
        """
        from app.application.analytics.bundle_tracking_service import BundleTrackingService

        try:
            await BundleTrackingService().track_event(
                store_id=store_id,
                event="promo_applied",
                promo_code=code,
            )
        except Exception as exc:
            logger.warning("Failed to record promo_applied for store %s: %s", store_id, exc)
            return False
        return True

    async def _find_coupon_connection(self, store_id: str) -> IntegrationConnection | None:
        connections = await self._connection_repo.find_many(
            {"store_id": store_id, "status": ConnectionStatus.ACTIVE.value}
        )
        for connection in connections:
            entity_types = {em.entity_type for em in (connection.entity_mappings or [])}
            if entity_types & COUPON_ENTITY_TYPES:
                return connection
        return None

    def _find_coupon_create_endpoint(self, connection: IntegrationConnection) -> dict | None:
        for ep in connection.discovered_endpoints or []:
            if not isinstance(ep, dict):
                continue
            method = str(ep.get("method", "")).upper()
            path = str(ep.get("path", ""))
            if method != "POST" or not path:
                continue
            endpoint_schema = EndpointSchema(
                path=path,
                method=method,
                operation_id=ep.get("operation_id"),
                summary=ep.get("summary"),
            )
            classified = self._classifier.classify(endpoint_schema)
            if classified and classified.entity_type in COUPON_ENTITY_TYPES:
                return ep
            if any(keyword in path.lower() for keyword in ("coupon", "discount", "promotion")):
                return ep
        return None

    def _build_coupon_payload(
        self,
        connection: IntegrationConnection,
        endpoint: dict,
        code: str,
        product_ids: list[str],
        discount_pct: float,
    ) -> dict[str, Any]:
        schema_fields = self._coupon_schema_fields(connection, endpoint)
        payload: dict[str, Any] = {}

        code_key = next((a for a in _CODE_FIELD_ALIASES if a in schema_fields), None)
        if code_key:
            payload[code_key] = code

        pct_key = next((a for a in _PERCENTAGE_FIELD_ALIASES if a in schema_fields), None)
        if pct_key:
            payload[pct_key] = discount_pct

        scope_key = next((a for a in _PRODUCT_SCOPE_ALIASES if a in schema_fields), None)
        if scope_key:
            payload[scope_key] = product_ids

        if not schema_fields:
            # Unknown schema: best-effort canonical payload. `code` must be set
            # (validated by the caller) or no promo code is shown.
            payload.setdefault("code", code)
            payload.setdefault("value", discount_pct)

        return payload

    def _coupon_schema_fields(self, connection: IntegrationConnection, endpoint: dict) -> set[str]:
        discovered = connection.discovered_schemas or {}
        key = f"{str(endpoint.get('method', '')).upper()} {endpoint.get('path', '')}"
        entry = discovered.get(key)
        if isinstance(entry, dict):
            fields = {str(f["name"]) for f in entry.get("fields", []) if isinstance(f, dict) and f.get("name")}
            if fields:
                return fields

        raw = connection.raw_spec or {}
        return self._request_body_fields(raw, endpoint.get("path", ""))

    @staticmethod
    def _request_body_fields(raw_spec: dict, path: str) -> set[str]:
        """Flatten the POST request body schema property names from the raw spec."""
        paths = raw_spec.get("paths", {}) if isinstance(raw_spec, dict) else {}
        path_item = paths.get(path) if isinstance(paths, dict) else None
        operation = (path_item or {}).get("post") if isinstance(path_item, dict) else None
        if not isinstance(operation, dict):
            return set()
        request_body = operation.get("requestBody") or {}
        content = request_body.get("content") or {}
        schema: dict = {}
        for media in content.values():
            candidate = (media or {}).get("schema")
            if candidate:
                schema = candidate or {}
                break
        if not schema:
            return set()

        schemas = ((raw_spec.get("components") or {}).get("schemas")) or (raw_spec.get("definitions") or {})
        return PromoCodeService._collect_property_names(schemas, schema)

    @staticmethod
    def _collect_property_names(schemas: dict, schema: dict, seen: set | None = None) -> set[str]:
        if seen is None:
            seen = set()
        if not isinstance(schema, dict) or id(schema) in seen:
            return set()
        seen.add(id(schema))
        ref = schema.get("$ref")
        if ref:
            name = str(ref).rsplit("/", 1)[-1]
            target = schemas.get(name)
            if target is not None:
                return PromoCodeService._collect_property_names(schemas, target, seen)
            return set()
        if "allOf" in schema:
            result: set[str] = set()
            for sub in schema.get("allOf", []):
                result |= PromoCodeService._collect_property_names(schemas, sub, seen)
            return result
        props = schema.get("properties")
        if not isinstance(props, dict):
            return set()
        result: set[str] = set()
        for prop_name, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                continue
            if prop_schema.get("type") in ("object", "array"):
                sub = prop_schema.get("items") if prop_schema.get("type") == "array" else prop_schema
                if isinstance(sub, dict) and sub.get("properties"):
                    result |= PromoCodeService._collect_property_names(schemas, sub, seen)
                else:
                    result.add(prop_name)
            else:
                result.add(prop_name)
        return result

    def _build_client(self, connection: IntegrationConnection) -> ExternalApiClient:
        base_url = self._resolve_base_url(connection)
        if not base_url:
            raise ValueError("No base URL found in the platform connection.")
        credentials = None
        if connection.encrypted_credentials:
            try:
                credentials = self._key_manager.decrypt_secret(connection.encrypted_credentials)
            except Exception as exc:
                logger.warning("Failed to decrypt platform credentials for store %s: %s", connection.store_id, exc)
        return ExternalApiClient(
            config=ConnectionConfig(base_url=base_url, timeout=15.0, max_retries=1),
            auth_config=connection.auth_config,
            encrypted_credentials=credentials,
            auth_handler=self._auth_handler,
        )

    @staticmethod
    def _extract_coupon_code(response: Any) -> str | None:
        if not isinstance(response, dict):
            return None
        for key in _CODE_FIELD_ALIASES:
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _resolve_base_url(connection: IntegrationConnection) -> str:
        raw_spec = connection.raw_spec or {}
        servers = raw_spec.get("servers", []) if isinstance(raw_spec, dict) else []
        candidates: list[str] = []
        if servers and isinstance(servers[0], dict):
            for entry in servers:
                if isinstance(entry, dict) and entry.get("url"):
                    candidates.append(str(entry["url"]).rstrip("/"))
        for ep in connection.discovered_endpoints or []:
            if isinstance(ep, dict):
                server = ep.get("server") or ep.get("base_url") or ep.get("url")
                if server:
                    candidates.append(str(server).rstrip("/"))
        for url in candidates:
            if not url:
                continue
            try:
                assert_safe_http_url(url)
            except Exception:
                logger.warning("Skipping unsafe base URL candidate '%s'", url)
                continue
            return url
        return ""
