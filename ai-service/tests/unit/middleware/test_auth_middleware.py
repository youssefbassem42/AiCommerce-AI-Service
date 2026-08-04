"""Tests for AuthMiddleware."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt as pyjwt
import pytest
from fastapi import Request, Response

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"


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
        headers_raw = []
        if auth_header:
            headers_raw.append((b"authorization", auth_header.encode()))
        scope["headers"] = headers_raw
        request = Request(scope)
    return request


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
        """Preconditions: Valid JWT in header. Input: Request with Bearer token. Execution: Dispatch. Expected: State set correctly."""
        secret = "test-secret"
        payload = {
            "sub": "user-1",
            "email": "user-1@example.com",
            "store_id": "store-1",
            "organization_id": "org-1",
            "roles": ["Seller"],
            "scopes": ["read"],
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, secret, algorithm="HS256")

        with (
            patch("app.middleware.auth.auth_settings.JWT_SECRET_KEY", secret),
            patch("app.middleware.auth.auth_settings.JWT_ALGORITHM", "HS256"),
            patch("app.middleware.auth.auth_settings.JWT_ISSUER", ISSUER),
            patch("app.middleware.auth.auth_settings.JWT_AUDIENCE", AUDIENCE),
            patch("app.middleware.auth.auth_settings.JWT_REQUIRED", True),
        ):
            request = create_mock_request(path="/api/v1/chat", auth_header=f"Bearer {token}")
            middleware = AuthMiddleware(lambda app: None)

            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            await middleware.dispatch(request, call_next)
            assert request.state.user_id == "user-1"
            assert request.state.store_id == "store-1"
            assert request.state.organization_id == "org-1"
            assert request.state.email == "user-1@example.com"
            assert request.state.roles == ["admin"]
            assert request.state.scopes == ["read"]

    @pytest.mark.asyncio
    async def test_expired_jwt_returns_401(self):
        """Preconditions: Expired JWT. Input: Request with expired token. Execution: Dispatch. Expected: 401."""
        secret = "test-secret"
        payload = {
            "sub": "user-1",
            "iss": ISSUER,
            "aud": AUDIENCE,
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = pyjwt.encode(payload, secret, algorithm="HS256")

        with (
            patch("app.middleware.auth.auth_settings.JWT_SECRET_KEY", secret),
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


from app.middleware.auth import AuthMiddleware
