from collections.abc import Callable
from functools import lru_cache

from fastapi import HTTPException, Request, status

from app.core.security import ERR_INSUFFICIENT, ERR_MISSING_HEADER, ERR_NO_ORG, ERR_NO_STORE
from app.domain.auth.entities.authenticated_user import AuthenticatedUser


@lru_cache
def get_audit_log_repository():
    from app.infrastructure.mongodb.repositories.audit_log_repository import AuditLogRepository

    return AuditLogRepository()


def get_current_user(request: Request) -> AuthenticatedUser:
    """Build the typed current user from the validated token (populated by AuthMiddleware)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
    return user


def get_current_store_id(request: Request) -> str:
    """Store ID from the validated JWT `store_id` claim only (contract §9)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
    if not user.has_store:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_STORE)
    return str(user.store_id)


def get_current_organization_id(request: Request) -> str:
    """Organization ID from the validated JWT `org_id` claim only (contract §9)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
    if not user.has_organization:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_ORG)
    return str(user.organization_id)


def get_optional_organization_id(request: Request) -> str | None:
    """Organization ID from the JWT `org_id` claim when present, else None."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
    return str(user.organization_id) if user.has_organization else None


def require_role(role: str) -> Callable[[Request], None]:
    """Require the exact internal role (`admin` or `super_admin`).

    Role checks are exact — SuperAdmin does not satisfy an Admin role check (contract §6:
    the SuperAdmin bypass applies to permissions, not roles).
    """

    def _require_role(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
        roles = getattr(request.state, "roles", [])
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_INSUFFICIENT)

    return _require_role


def require_admin_role(request: Request):
    """Require the `admin` role (store-level). Exact match per contract §6."""
    return require_role("admin")(request)


def require_super_admin_role(request: Request):
    """Require the `super_admin` role (platform-level). Exact match per contract §6."""
    return require_role("super_admin")(request)


def require_permission(permission: str) -> Callable[[Request], None]:
    """Require a `permission` claim (contract §6).

    SuperAdmin automatically passes ALL permission checks.
    """

    def _require_permission(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERR_MISSING_HEADER)
        if user.is_super_admin:
            return
        if permission not in user.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_INSUFFICIENT)

    return _require_permission
