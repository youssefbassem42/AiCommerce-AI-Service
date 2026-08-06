"""Tests for AuthMiddleware."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import Request, Response

from app.core.security import ROLE_CLAIM

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"

USER_GUID = "11111111-1111-1111-1111-111111111111"
STORE_GUID = "22222222-2222-2222-2222-222222222222"
ORG_GUID = "33333333-3333-3333-3333-333333333333"


def create_mock_request(path="/api/v1/chat", auth_header=None, method="GET"):
    scope = {
        "type": "http",
        "path": path,
        "method": method,
        "headers": [],
        "client": ("127.0.0.1", 8000),
    }
    request = Request(scope)
    if auth_header:
        scope["headers"] = [(b"authorization", auth_header.encode())]
        request = Request(scope)
    return request


def _contract_token(secret: str, **overrides) -> str:
    payload = {
        "sub": USER_GUID,
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier": USER_GUID,
        "email": "user-1@example.com",
        "security_stamp": "test-security-stamp",
        "store_id": STORE_GUID,
        "org_id": ORG_GUID,
        ROLE_CLAIM: "Admin",
        "permission": ["kb:read"],
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    payload.update(overrides)
    return pyjwt.encode(payload, secret, algorithm="HS256")


class TestAuthMiddleware:
    """Purpose: Validate JWT middleware behavior."""

    @pytest.mark.asyncio
    async def test_whitelisted_path_skips_auth(self):
        """Preconditions: Request to /health. Input: No auth header. Execution: Dispatch. Expected: 200."""
        request = create_mock_request(path="/health/")
        middleware = AuthMiddleware(lambda app: None)
        call_next = AsyncMock(return_value=Response("OK", status_code=200))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_auth_header_with_jwt_required(self):
        """Preconditions: JWT required, no auth header. Input: Request to protected path. Execution: Dispatch. Expected: 401."""
        with patch("app.middleware.auth.auth_settings.JWT_REQUIRED", True):
            request = create_mock_request(path="/api/v1/chat")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_auth_header_with_jwt_not_required(self):
        """Preconditions: JWT not required, no auth header. Input: Request. Execution: Dispatch. Expected: 200."""
        with patch("app.middleware.auth.auth_settings.JWT_REQUIRED", False):
            request = create_mock_request(path="/api/v1/chat")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_valid_jwt_sets_state(self):
        """Preconditions: Valid contract JWT in header. Input: Request with Bearer token. Execution: Dispatch. Expected: State set from claims."""
        secret = "test-secret-that-is-long-enough"
        token = _contract_token(secret)

        with (
            patch("app.middleware.auth.auth_settings.JWT_SECRET", secret),
            patch("app.middleware.auth.auth_settings.JWT_ALGORITHM", "HS256"),
            patch("app.middleware.auth.auth_settings.JWT_ISSUER", ISSUER),
            patch("app.middleware.auth.auth_settings.JWT_AUDIENCE", AUDIENCE),
            patch("app.middleware.auth.auth_settings.JWT_REQUIRED", True),
        ):
            request = create_mock_request(path="/api/v1/chat", auth_header=f"Bearer {token}")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            await middleware.dispatch(request, call_next)
            assert request.state.user_id == USER_GUID
            assert request.state.store_id == STORE_GUID
            assert request.state.organization_id == ORG_GUID
            assert request.state.email == "user-1@example.com"
            assert request.state.roles == ["admin"]
            assert request.state.permissions == ["kb:read"]
            assert request.state.user is not None

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_401(self):
        """Preconditions: Expired JWT. Input: Request with expired token. Execution: Dispatch. Expected: 401."""
        secret = "test-secret-that-is-long-enough"
        token = _contract_token(secret, exp=datetime.now(UTC) - timedelta(hours=1))

        with (
            patch("app.middleware.auth.auth_settings.JWT_SECRET", secret),
            patch("app.middleware.auth.auth_settings.JWT_ALGORITHM", "HS256"),
            patch("app.middleware.auth.auth_settings.JWT_ISSUER", ISSUER),
            patch("app.middleware.auth.auth_settings.JWT_AUDIENCE", AUDIENCE),
        ):
            request = create_mock_request(path="/api/v1/chat", auth_header=f"Bearer {token}")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_jwt_returns_401(self):
        """Preconditions: Invalid JWT string. Input: Garbage token. Execution: Dispatch. Expected: 401."""
        with patch("app.middleware.auth.auth_settings.JWT_REQUIRED", True):
            request = create_mock_request(path="/api/v1/chat", auth_header="Bearer invalid-token")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix(self):
        """Preconditions: Auth header without Bearer prefix. Input: "Token xxx". Execution: Dispatch. Expected: 401."""
        with patch("app.middleware.auth.auth_settings.JWT_REQUIRED", True):
            request = create_mock_request(path="/api/v1/chat", auth_header="Token xyz")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_non_bearer_format_rejected_even_when_not_required(self):
        """Pass a malformed header with JWT_REQUIRED off. A present token is still rejected (401)."""
        request = create_mock_request(path="/api/v1/chat", auth_header="ApiKey abc")
        middleware = AuthMiddleware(lambda app: None)

        call_next = AsyncMock(return_value=Response("OK", status_code=200))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 401


from app.middleware.auth import AuthMiddleware
