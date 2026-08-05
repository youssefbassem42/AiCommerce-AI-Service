import logging
from typing import Any

from app.domain.knowledge.value_objects.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class TenantContextResolver:
    """Authoritative resolver for the tenant context of an authenticated request.

    Single source of truth for tenant identity. Input is either the validated
    JWT claims exposed by AuthMiddleware on request.state, or an encoded JWT
    when the middleware is not in the request path (workers, tests, CLI).
    """

    @staticmethod
    def from_claims(payload: dict[str, Any]) -> TenantContext:
        """Resolve tenant from pre-validated JWT claims (request.state).

        Expects keys: organization_id (or org_id), store_id (or tenant_id),
        and optional merchant_id, store_slug, language, currency, timezone,
        knowledge_version, vector_namespace.
        """
        org_id = payload.get("organization_id") or payload.get("org_id")
        store_id = payload.get("store_id") or payload.get("tenant_id")
        if not org_id or not store_id:
            raise ValueError("JWT claims missing organization_id and store_id")

        vector_ns = payload.get("vector_namespace") or store_id
        return TenantContext(
            organization_id=org_id,
            store_id=store_id,
            merchant_id=payload.get("merchant_id") or payload.get("merchant", ""),
            integration_id=payload.get("integration_id", ""),
            store_slug=payload.get("store_slug", ""),
            language=payload.get("language", "en"),
            currency=payload.get("currency", "USD"),
            timezone=payload.get("timezone", "UTC"),
            knowledge_version=int(payload.get("knowledge_version", 1)),
            vector_namespace=vector_ns,
        )

    @classmethod
    def from_jwt(cls, token: str) -> TenantContext:
        """Resolve tenant from an encoded JWT using verified decoding."""
        from app.core.security import decode_jwt

        try:
            payload: dict[str, Any] = decode_jwt(token)
        except Exception:
            raise ValueError("Invalid JWT token")
        return cls.from_claims(payload)
