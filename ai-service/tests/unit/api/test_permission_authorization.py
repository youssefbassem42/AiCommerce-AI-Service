"""Authorization parity with .NET's PermissionAuthorizationHandler and role checks.

.NET semantics replicated here:
- Permission policies (Permissions.All) succeed when the principal has a matching
  `permission` claim OR holds the SuperAdmin role (handler bypass).
- Role checks ([Authorize(Roles=...)]) are exact IsInRole matches against any of the
  role claims — SuperAdmin does NOT satisfy an Admin role check.
- Tenant identity comes from JWT claims only (store_id), never from the request body.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import Request

from app.core.security import ROLE_CLAIM, SECURITY_STAMP_CLAIM

USER_GUID = "11111111-1111-1111-1111-111111111111"
STORE_GUID = "22222222-2222-2222-2222-222222222222"
SECRET = "test-jwt-secret-shared-0123456789abcdef"


def _token(*, roles: list[str] | None = None, permissions: list[str] | None = None, store_id: str | None = STORE_GUID):
    payload: dict = {
        "sub": USER_GUID,
        "email": "user@example.com",
        SECURITY_STAMP_CLAIM: "stamp",
        "iss": "AI-Sales-Agent",
        "aud": "AI-Sales-Agent",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if roles:
        payload[ROLE_CLAIM] = roles if len(roles) > 1 else roles[0]
    if permissions:
        payload["permission"] = permissions
    if store_id is not None:
        payload["store_id"] = store_id
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


def _request_with_user(token: str) -> Request:
    from app.application.auth.jwt_service import jwt_validation_service

    user = jwt_validation_service.validate(token)
    scope = {"type": "http", "path": "/x", "method": "GET", "headers": []}
    request = Request(scope)
    request.state.user = user
    request.state.user_id = str(user.user_id)
    request.state.roles = user.roles or ([user.role] if user.role else [])
    request.state.store_id = str(user.store_id) if user.store_id else None
    request.state.organization_id = str(user.organization_id) if user.organization_id else None
    return request


@pytest.fixture(autouse=True)
def _settings():
    with (
        patch("app.core.security.auth_settings.JWT_SECRET", SECRET),
        patch("app.core.security.auth_settings.JWT_ALGORITHM", "HS256"),
        patch("app.core.security.auth_settings.JWT_ISSUER", "AI-Sales-Agent"),
        patch("app.core.security.auth_settings.JWT_AUDIENCE", "AI-Sales-Agent"),
    ):
        yield


from app.api.auth.dependencies import (  # noqa: E402
    get_current_store_id,
    require_admin_role,
    require_permission,
    require_super_admin_role,
)


class TestPermissionAuthorization:
    """Mirrors .NET PermissionAuthorizationHandler (permission claim OR SuperAdmin bypass)."""

    def test_permission_claim_grants_access(self):
        token = _token(roles=["Admin"], permissions=["Stores.Read", "Users.Manage"])
        request = _request_with_user(token)
        require_permission("Stores.Read")(request)

    def test_missing_permission_denied(self):
        from fastapi import HTTPException

        token = _token(roles=["Admin"], permissions=["Stores.Read"])
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            require_permission("Users.Manage")(request)
        assert exc_info.value.status_code == 403

    def test_no_permissions_denied(self):
        from fastapi import HTTPException

        token = _token(roles=["Admin"], permissions=[])
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            require_permission("Stores.Read")(request)
        assert exc_info.value.status_code == 403

    def test_super_admin_bypasses_all_permissions(self):
        token = _token(roles=["SuperAdmin"], permissions=[])
        request = _request_with_user(token)
        require_permission("Users.Manage")(request)
        require_permission("Subscriptions.Manage")(request)


class TestRoleAuthorization:
    """Mirrors .NET [Authorize(Roles=...)] exact IsInRole semantics."""

    def test_multiple_roles_any_matches(self):
        token = _token(roles=["Seller", "Admin"])
        request = _request_with_user(token)
        require_admin_role(request)

    def test_admin_does_not_satisfy_super_admin(self):
        from fastapi import HTTPException

        token = _token(roles=["Admin"])
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            require_super_admin_role(request)
        assert exc_info.value.status_code == 403

    def test_super_admin_does_not_satisfy_admin(self):
        from fastapi import HTTPException

        token = _token(roles=["SuperAdmin"])
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(request)
        assert exc_info.value.status_code == 403

    def test_no_roles_denied(self):
        from fastapi import HTTPException

        token = _token(roles=[])
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(request)
        assert exc_info.value.status_code == 403


class TestTenantIsolation:
    """store_id comes from the JWT claim only — 403 when absent, never from the body."""

    def test_store_id_from_claim(self):
        token = _token(store_id=STORE_GUID)
        request = _request_with_user(token)
        assert get_current_store_id(request) == STORE_GUID

    def test_missing_store_id_forbidden(self):
        from fastapi import HTTPException

        token = _token(store_id=None)
        request = _request_with_user(token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_store_id(request)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "No store associated with this account"

    def test_multi_role_user_keeps_store_guid_identity(self):
        token = _token(roles=["Seller", "Admin"], store_id=STORE_GUID)
        request = _request_with_user(token)
        assert uuid.UUID(request.state.user_id) == uuid.UUID(USER_GUID)
        assert request.state.store_id == STORE_GUID
