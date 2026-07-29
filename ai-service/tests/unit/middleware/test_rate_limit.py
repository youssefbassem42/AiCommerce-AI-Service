"""Tests for extended RateLimitMiddleware per-tenant rate limiting."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request, Response

from app.middleware.rate_limit import RateLimitMiddleware


def create_mock_request(path="/api/v1/chat", tenant_id=None):
    scope = {
        "type": "http",
        "path": path,
        "method": "GET",
        "headers": [],
        "client": ("10.0.0.1", 8000),
    }
    request = Request(scope)
    if tenant_id is not None:
        request.state.tenant_id = tenant_id
    return request


class TestRateLimitMiddleware:
    """Purpose: Validate per-tenant rate limiting key derivation."""

    def test_rate_limit_key_with_tenant(self):
        """Preconditions: Request has tenant_id in state. Input: Request with tenant. Execution: _get_rate_limit_key. Expected: Tenant-based key."""
        request = create_mock_request(tenant_id="store-1")
        middleware = RateLimitMiddleware(lambda app: None, limit_per_minute=100)
        key = middleware._get_rate_limit_key(request)
        assert key == "tenant:store-1"

    def test_rate_limit_key_without_tenant(self):
        """Preconditions: No tenant_id in state. Input: Request without tenant. Execution: _get_rate_limit_key. Expected: IP-based key."""
        request = create_mock_request(tenant_id=None)
        middleware = RateLimitMiddleware(lambda app: None, limit_per_minute=100)
        key = middleware._get_rate_limit_key(request)
        assert key.startswith("ip:")

    @pytest.mark.asyncio
    async def test_whitelisted_path_skips_rate_limit(self):
        """Preconditions: Request to /health. Input: GET /health/. Execution: Dispatch. Expected: Passes through."""
        request = create_mock_request(path="/health/")
        middleware = RateLimitMiddleware(lambda app: None, limit_per_minute=100)

        call_next = AsyncMock(return_value=Response("OK", status_code=200))
        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200
