"""End-to-end compatibility with the exact JWT layout the .NET backend issues.

Reconstructs the JSON payload that AI_Sales_Agent.Infrastructure.Auth.JwtTokenService
writes (ASP.NET long-form claim URIs + short JWT-registered claims + `security_stamp`)
and asserts the FastAPI resource-server layer accepts the .NET token and rejects every
category of invalid token the same way the .NET JwtBearerOptions does.
"""

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest

from app.core.security import EMAIL_CLAIM, NAME_IDENTIFIER_CLAIM, ROLE_CLAIM, SECURITY_STAMP_CLAIM

ISSUER = "AI-Sales-Agent"
AUDIENCE = "AI-Sales-Agent"
SECRET = "test-jwt-secret-shared-0123456789abcdef"

USER_GUID = "11111111-1111-1111-1111-111111111111"
STORE_GUID = "22222222-2222-2222-2222-222222222222"
ORG_GUID = "33333333-3333-3333-3333-333333333333"


def dotnet_token(
    *,
    role: str | None = "Admin",
    store_id: str | None = STORE_GUID,
    org_id: str | None = ORG_GUID,
    permissions: list[str] | None = None,
    secret: str = SECRET,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    **overrides,
) -> str:
    """Build a token byte-for-byte like .NET's JwtTokenService.CreateTokenAsync.

    Claim set mirrors JwtTokenService 1:1: sub + ClaimTypes.NameIdentifier URI, email +
    ClaimTypes.Email URI, security_stamp, jti, iat, optional store_id, role URI claim(s)
    and arbitrary user claims ("permission").
    """
    payload: dict = {
        "sub": USER_GUID,
        NAME_IDENTIFIER_CLAIM: USER_GUID,
        "email": "admin@example.com",
        EMAIL_CLAIM: "admin@example.com",
        SECURITY_STAMP_CLAIM: "aspnet-security-stamp-123",
        "jti": "6f5cbf6f-4b3f-4a9a-9b31-6a5f5b0f0f0a",
        "iat": int(datetime.now(UTC).timestamp()),
        "iss": issuer,
        "aud": audience,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if store_id is not None:
        payload["store_id"] = store_id
    if org_id is not None:
        payload["org_id"] = org_id
    if role is not None:
        payload[ROLE_CLAIM] = role
    if permissions:
        payload["permission"] = permissions
    payload.update(overrides)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="module")
def client():

    from fastapi.testclient import TestClient

    from app.main import app

    yield TestClient(app)


def test_dotnet_token_list_models(client):
    """A .NET-issued token with the exact claim layout can call a protected AI endpoint."""
    headers = {"Authorization": f"Bearer {dotnet_token()}"}
    resp = client.get("/api/v1/ai/models", headers=headers)
    assert resp.status_code == 200


def test_dotnet_token_guarded_knowledge_endpoint(client):
    """A .NET Admin token is authorized on admin-guarded endpoints (IsInRole equivalent)."""
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
    try:
        resp = client.get(
            "/api/v1/knowledge-base/documents",
            headers={"Authorization": f"Bearer {dotnet_token()}"},
        )
        assert resp.status_code == 200
    finally:
        client.app.dependency_overrides.clear()


def test_invalid_signature_rejected(client):
    resp = client.get(
        "/api/v1/ai/models",
        headers={"Authorization": f"Bearer {dotnet_token(secret='a-different-secret-0123456789abcdef')}"},
    )
    assert resp.status_code == 401


def test_invalid_issuer_rejected(client):
    resp = client.get(
        "/api/v1/ai/models",
        headers={"Authorization": f"Bearer {dotnet_token(issuer='evil-issuer')}"},
    )
    assert resp.status_code == 401


def test_invalid_audience_rejected(client):
    resp = client.get(
        "/api/v1/ai/models",
        headers={"Authorization": f"Bearer {dotnet_token(audience='wrong-audience')}"},
    )
    assert resp.status_code == 401


def test_expired_token_rejected(client):
    resp = client.get(
        "/api/v1/ai/models",
        headers={
            "Authorization": f"Bearer {dotnet_token(exp=datetime.now(UTC) - timedelta(hours=1))}"
        },
    )
    assert resp.status_code == 401


def test_missing_security_stamp_rejected(client):
    """A token without the `security_stamp` claim is rejected (mirrors .NET OnTokenValidated)."""
    token = dotnet_token()
    payload = pyjwt.decode(token, SECRET, algorithms=["HS256"], options={"verify_aud": False, "verify_iss": False})
    payload.pop(SECURITY_STAMP_CLAIM)
    raw = pyjwt.encode(payload, SECRET, algorithm="HS256")
    resp = client.get(
        "/api/v1/ai/models",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert resp.status_code == 401


def test_missing_required_claim_rejected(client):
    payload = pyjwt.decode(dotnet_token(), SECRET, algorithms=["HS256"], options={"verify_aud": False, "verify_iss": False})
    payload.pop("sub")
    raw = pyjwt.encode(payload, SECRET, algorithm="HS256")
    resp = client.get(
        "/api/v1/ai/models",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert resp.status_code == 401


def test_seller_role_denied_admin_endpoint(client):
    resp = client.get(
        "/api/v1/auth/audit-logs",
        headers={"Authorization": f"Bearer {dotnet_token(role='Seller')}"},
    )
    assert resp.status_code == 403


def test_admin_role_denied_super_admin_endpoint(client):
    resp = client.get(
        "/api/v1/auth/audit-logs",
        headers={"Authorization": f"Bearer {dotnet_token(role='Admin')}"},
    )
    assert resp.status_code == 403


def test_super_admin_allowed_super_admin_endpoint(client):
    from unittest.mock import AsyncMock, MagicMock

    from app.api.auth.dependencies import get_audit_log_repository

    repo = MagicMock()
    repo.find_many = AsyncMock(return_value=[])
    client.app.dependency_overrides[get_audit_log_repository] = lambda: repo
    try:
        resp = client.get(
            "/api/v1/auth/audit-logs",
            headers={"Authorization": f"Bearer {dotnet_token(role='SuperAdmin')}"},
        )
        assert resp.status_code == 200
    finally:
        client.app.dependency_overrides.clear()
