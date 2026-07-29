"""Tests for AuditMiddleware."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Request, Response

from app.middleware.audit import AuditMiddleware


def create_mock_request(path="/api/v1/chat", method="POST"):
    scope = {
        "type": "http",
        "path": path,
        "method": method,
        "headers": [],
        "client": ("127.0.0.1", 8000),
    }
    request = Request(scope)
    return request


class TestAuditMiddleware:
    """Purpose: Validate audit logging middleware behavior."""

    @pytest.mark.asyncio
    async def test_health_path_skips_audit(self):
        """Preconditions: Request to /health. Input: GET /health/. Execution: Dispatch. Expected: No audit log created."""
        request = create_mock_request(path="/health/")
        middleware = AuditMiddleware(lambda app: None)


        with patch.object(middleware, "_log_audit_entry") as mock_log:
            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_request_skips_audit(self):
        """Preconditions: GET request. Input: GET /api/v1/data. Execution: Dispatch. Expected: No audit log."""
        request = create_mock_request(path="/api/v1/data", method="GET")
        middleware = AuditMiddleware(lambda app: None)


        with patch.object(middleware, "_log_audit_entry") as mock_log:
            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200
            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_request_logs_audit(self):
        """Preconditions: POST request to protected path. Input: POST /api/v1/chat. Execution: Dispatch. Expected: Audit log created."""
        request = create_mock_request(path="/api/v1/chat", method="POST")
        middleware = AuditMiddleware(lambda app: None)


        with patch.object(middleware, "_log_audit_entry") as mock_log:
            call_next = AsyncMock(return_value=Response("OK", status_code=200))
            response = await middleware.dispatch(request, call_next)
            assert response.status_code == 200
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_request_logs_failure(self):
        """Preconditions: Request that fails. Input: POST causing 500. Execution: Dispatch. Expected: Audit log for failure."""
        request = create_mock_request(path="/api/v1/chat", method="POST")
        middleware = AuditMiddleware(lambda app: None)


        with patch.object(middleware, "_log_audit_entry") as mock_log:
            call_next = AsyncMock(side_effect=ValueError("DB error"))
            with pytest.raises(ValueError):
                await middleware.dispatch(request, call_next)
            mock_log.assert_called_once()
