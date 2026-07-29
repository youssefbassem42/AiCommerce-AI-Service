from typing import Optional


class TenantContextResolver:
    """Resolves tenant context from authentication state."""

    @staticmethod
    def resolve(request) -> Optional[str]:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return tenant_id
        headers = request.headers
        tenant_id = headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id
        return None

    @staticmethod
    def resolve_from_jwt(payload: dict) -> Optional[str]:
        return payload.get("tenant_id") or payload.get("store_id") or payload.get("sub")

    @staticmethod
    def resolve_from_api_key(api_key_entity) -> Optional[str]:
        return api_key_entity.store_id if api_key_entity else None
