from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.api.ticket.dependencies import get_ticket_service
from app.core.auth_settings import auth_settings
from app.main import app
from app.middleware.audit import AuditMiddleware


def _admin_headers(store_id: str = "22222222-2222-2222-2222-222222222222") -> dict[str, str]:
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "security_stamp": "test-security-stamp",
        "store_id": store_id,
        "organization_id": "33333333-3333-3333-3333-333333333333",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": "Admin",
        "iss": auth_settings.JWT_ISSUER,
        "aud": auth_settings.JWT_AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = pyjwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(app, raise_server_exceptions=False, headers=_admin_headers())


@pytest.fixture
def mock_ticket_service():
    svc = MagicMock()
    svc.get_ticket = AsyncMock(return_value=None)
    return svc


class TestTicketStoreIsolation:
    def test_get_ticket_from_other_store_returns_404(self, client, mock_ticket_service):
        ticket = MagicMock()
        ticket.store_id = "other-store"
        ticket.model_dump.return_value = {"store_id": "other-store"}
        mock_ticket_service.get_ticket = AsyncMock(return_value=ticket)

        app.dependency_overrides[get_ticket_service] = lambda: mock_ticket_service
        try:
            response = client.get("/api/v1/tickets/ticket-123")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    def test_get_ticket_from_own_store_returns_200(self, client, mock_ticket_service):
        now = datetime.now(UTC)
        ticket = MagicMock()
        ticket.store_id = "22222222-2222-2222-2222-222222222222"
        ticket.model_dump.return_value = {
            "id": "ticket-id-1",
            "ticket_id": "ticket-123",
            "store_id": "22222222-2222-2222-2222-222222222222",
            "customer_id": "cust-1",
            "sentiment": "neutral",
            "category": "support",
            "summary": "s",
            "priority": "low",
            "status": "open",
            "suggested_response": "",
            "analyzed_at": now,
            "created_at": now,
            "updated_at": now,
            "customer": None,
            "recent_orders": [],
            "conversation": None,
            "messages": [],
            "assigned_to": None,
            "eta": None,
        }
        mock_ticket_service.get_ticket = AsyncMock(return_value=ticket)

        app.dependency_overrides[get_ticket_service] = lambda: mock_ticket_service
        try:
            response = client.get("/api/v1/tickets/ticket-123")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()

    def test_delete_ticket_from_other_store_returns_404(self, client, mock_ticket_service):
        ticket = MagicMock()
        ticket.store_id = "other-store"
        mock_ticket_service.get_ticket = AsyncMock(return_value=ticket)

        app.dependency_overrides[get_ticket_service] = lambda: mock_ticket_service
        try:
            response = client.delete("/api/v1/tickets/ticket-123")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
