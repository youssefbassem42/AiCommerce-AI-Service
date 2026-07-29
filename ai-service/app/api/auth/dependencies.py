from fastapi import Depends, HTTPException, Request, status

from app.infrastructure.mongodb.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository


def get_api_key_repository() -> ApiKeyRepository:
    return ApiKeyRepository()


def get_audit_log_repository() -> AuditLogRepository:
    return AuditLogRepository()


def get_current_tenant(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant context not found")
    return tenant_id


def require_role(role: str):
    def _require_role(request: Request) -> None:
        roles = getattr(request.state, "roles", [])
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing required role: {role}")
    return _require_role


def require_scope(scope: str):
    def _require_scope(request: Request) -> None:
        scopes = getattr(request.state, "scopes", [])
        if scope not in scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing required scope: {scope}")
    return _require_scope
