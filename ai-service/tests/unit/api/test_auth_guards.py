"""Enforcement tests: contract-guarded routers reject anonymous and non-admin callers."""

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"
SECRET = "test-jwt-secret-shared-0123456789abcdef"

USER_GUID = "11111111-1111-1111-1111-111111111111"
STORE_GUID = "22222222-2222-2222-2222-222222222222"
ORG_GUID = "33333333-3333-3333-3333-333333333333"

ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"


def _token(role: str | None, *, store_id: str | None = STORE_GUID) -> str:
    payload = {
        "sub": USER_GUID,
        "email": "admin@example.com",
        "store_id": store_id,
        "org_id": ORG_GUID,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    if role:
        payload[ROLE_CLAIM] = role
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def no_overrides(client):
    client.app.dependency_overrides.clear()
    yield


def test_health_is_public(client):
    assert client.get("/health/").status_code == 200


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/integration/connections", "GET"),
        ("/api/v1/tickets", "GET"),
        ("/api/v1/knowledge-base/documents", "GET"),
        ("/api/v1/knowledge-base/search", "POST"),
        ("/knowledge/jobs", "GET"),
    ],
)
def test_guarded_routers_reject_anonymous(client, path, method):
    resp = client.request(method, path)
    assert resp.status_code == 401


def test_guarded_router_rejects_seller_role(client):
    token = _token("Seller")
    resp = client.get(
        "/api/v1/knowledge-base/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_guarded_router_accepts_admin_role(client):
    from unittest.mock import AsyncMock, MagicMock

    from pydantic import BaseModel

    from app.api.knowledge.dependencies import get_knowledge_document_service

    class _Page(BaseModel):
        items: list = []
        total: int = 0
        page: int = 1
        page_size: int = 20

    svc = MagicMock()
    svc.list = AsyncMock(return_value=_Page())
    client.app.dependency_overrides[get_knowledge_document_service] = lambda: svc

    token = _token("Admin")
    resp = client.get(
        "/api/v1/knowledge-base/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_admin_does_not_satisfy_super_admin(client):
    token = _token("Admin")
    resp = client.get("/api/v1/auth/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_super_admin_satisfies_super_admin(client):
    from unittest.mock import AsyncMock, MagicMock

    from app.api.auth.dependencies import get_audit_log_repository

    repo = MagicMock()
    repo.find_many = AsyncMock(return_value=[])
    client.app.dependency_overrides[get_audit_log_repository] = lambda: repo

    token = _token("SuperAdmin")
    resp = client.get("/api/v1/auth/audit-logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_missing_store_claim_forbidden(client):
    token = _token("Admin", store_id=None)
    resp = client.get(
        "/api/v1/knowledge-base/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "No store associated with this account"


def test_legacy_ai_commerce_token_rejected(client):
    legacy = pyjwt.encode(
        {
            "sub": USER_GUID,
            "store_id": STORE_GUID,
            "iss": "ai-commerce",
            "aud": "ai-service",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )
    resp = client.get(
        "/api/v1/knowledge-base/documents",
        headers={"Authorization": f"Bearer {legacy}"},
    )
    assert resp.status_code == 401


def test_public_rag_accepts_no_token(client):
    resp = client.post("/rag/chat", json={"message": "hello"})
    assert resp.status_code != 401
