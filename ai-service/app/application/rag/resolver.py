import logging
from typing import Any, Optional

from app.domain.knowledge.value_objects.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class TenantContextResolver:
    """Resolves the current tenant context from various authentication sources.

    Every resolution path returns a TenantContext so the caller never needs to
    know which Store, Organization, or Knowledge Base is active.
    """

    def __init__(
        self,
        store_registry: Optional[dict[str, dict[str, str]]] = None,
    ) -> None:
        self._registry = store_registry or {}

    def register_store(self, slug: str, config: dict[str, str]) -> None:
        self._registry[slug] = config

    @staticmethod
    def from_config(config: dict[str, str]) -> TenantContext:
        vector_ns = config.get("store_slug") or config.get("store_id", "")
        return TenantContext(
            organization_id=config["organization_id"],
            store_id=config["store_id"],
            merchant_id=config.get("merchant_id", ""),
            integration_id=config.get("integration_id", ""),
            store_slug=config.get("store_slug", ""),
            language=config.get("language", "en"),
            currency=config.get("currency", "USD"),
            timezone=config.get("timezone", "UTC"),
            knowledge_version=int(config.get("knowledge_version", 1)),
            vector_namespace=vector_ns,
        )

    def from_slug(self, slug: str) -> TenantContext:
        """Resolve tenant from a store slug (e.g. subdomain or CLI arg)."""
        config = self._registry.get(slug)
        if not config:
            available = ", ".join(self._registry)
            raise ValueError(f"Unknown store slug '{slug}'. Available: {available}")
        return self.from_config(config)

    def from_jwt(self, token: str) -> TenantContext:
        """Resolve tenant from an encoded JWT using verified decoding.

        Expects claims: organization_id, store_id, merchant_id, store_slug.
        Falls back to registry lookup if claims contain a store_slug.
        """
        from app.core.security import decode_jwt

        try:
            payload: dict[str, Any] = decode_jwt(token)
        except Exception:
            raise ValueError("Invalid JWT token")

        org_id = payload.get("organization_id") or payload.get("org_id")
        store_id = payload.get("store_id")
        if not org_id or not store_id:
            slug = payload.get("store_slug") or payload.get("slug", "")
            if slug and slug in self._registry:
                return self.from_slug(slug)
            raise ValueError("JWT missing organization_id and store_id")

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

    @staticmethod
    def from_claims(payload: dict[str, Any]) -> TenantContext:
        """Resolve tenant from pre-validated JWT claims dict.

        Expects keys: organization_id (or org_id), store_id, merchant_id, store_slug.
        This is the preferred entry point when the JWT has already been validated
        by the AuthMiddleware and claims are available via request.state.
        """
        org_id = payload.get("organization_id") or payload.get("org_id")
        store_id = payload.get("store_id")
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

    def from_api_key(self, api_key: str) -> TenantContext:
        """Resolve tenant from an API key.

        Matches against the registered store configs or an external
        API key → store mapping.
        """
        key_hash = _hash_key(api_key)
        for slug, config in self._registry.items():
            stored = config.get("api_key_hash", "")
            if stored and stored == key_hash:
                return self.from_config(config)
        raise ValueError(f"Unknown API key (hash={key_hash[:12]}...)")

    def from_webhook_payload(self, payload: dict[str, Any]) -> TenantContext:
        """Resolve tenant from a webhook event payload.

        Expects keys: organization_id, store_id, merchant_id, store_slug.
        """
        org_id = payload.get("organization_id") or payload.get("org_id")
        store_id = payload.get("store_id")
        if not org_id or not store_id:
            slug = payload.get("store_slug") or payload.get("slug", "")
            if slug and slug in self._registry:
                return self.from_slug(slug)
            raise ValueError("Webhook payload missing tenant identifiers")

        vector_ns = payload.get("vector_namespace") or store_id
        return TenantContext(
            organization_id=org_id,
            store_id=store_id,
            merchant_id=payload.get("merchant_id", ""),
            integration_id=payload.get("integration_id", ""),
            store_slug=payload.get("store_slug", ""),
            language=payload.get("language", "en"),
            currency=payload.get("currency", "USD"),
            timezone=payload.get("timezone", "UTC"),
            knowledge_version=int(payload.get("knowledge_version", 1)),
            vector_namespace=vector_ns,
        )

    def from_embed_widget(self, widget_config: dict[str, str]) -> TenantContext:
        """Resolve tenant from an embedded widget configuration.

        Widget provides store_slug and optionally language/currency.
        """
        slug = widget_config.get("store_slug") or widget_config.get("slug", "")
        if not slug:
            raise ValueError("Embed widget missing store_slug")
        return self.from_slug(slug)

    def from_admin_session(self, user_id: str) -> TenantContext:
        """Resolve tenant for an admin dashboard session.

        Uses the user's assigned store from the registry.
        """
        for slug, config in self._registry.items():
            if config.get("admin_user_id", "") == user_id:
                return self.from_config(config)
        raise ValueError(f"Admin user '{user_id}' is not assigned to any store")


def _hash_key(key: str) -> str:
    import hashlib
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
