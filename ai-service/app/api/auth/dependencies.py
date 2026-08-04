from fastapi import HTTPException, Request, status

from app.infrastructure.mongodb.repositories.api_key_repository import ApiKeyRepository
from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository


def get_api_key_repository() -> ApiKeyRepository:
    return ApiKeyRepository()


def get_audit_log_repository() -> AuditLogRepository:
    return AuditLogRepository()


def get_current_store_id(request: Request) -> str:
    store_id = getattr(request.state, "store_id", None)
    if not store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Store context not found")
    return store_id


def get_current_organization_id(request: Request) -> str | None:
    return getattr(request.state, "organization_id", None)


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


ADMIN_ROLES = {"admin", "store_admin"}


async def require_admin_role(request: Request) -> None:
    roles = getattr(request.state, "roles", [])
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: no roles assigned",
        )
    if "super_admin" in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: super admins cannot access store-level analytics",
        )
    if not any(r in ADMIN_ROLES for r in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: requires admin role",
        )


async def require_super_admin_role(request: Request) -> None:
    roles = getattr(request.state, "roles", [])
    if "super_admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: super admin role required",
        )
