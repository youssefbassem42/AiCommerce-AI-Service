import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["AZURE_OPENAI_KEY"] = "test-azure-key"
os.environ["AZURE_ENDPOINT"] = "https://test-endpoint.openai.azure.com"
os.environ["AZURE_DEPLOYMENT"] = "test-deployment"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["CLAUDE_API_KEY"] = "test-claude-key"
os.environ["OLLAMA_URL"] = "http://localhost:11434"
os.environ["DEEPSEEK_API_KEY"] = "test-deepseek-key"
os.environ["MISTRAL_API_KEY"] = "test-mistral-key"
os.environ["DEFAULT_PROVIDER"] = "openai"
os.environ["DEFAULT_MODEL"] = "gpt-4o-mini"
os.environ["REQUEST_TIMEOUT"] = "30.0"
os.environ["MAX_RETRIES"] = "1"
# Shared HS256 secret for tests. Fail-fast startup validation requires >= 32 chars.
os.environ["JWT_SECRET"] = "test-jwt-secret-shared-0123456789abcdef"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-shared-0123456789abcdef"
# Keep the shared in-memory rate limiter (wall-clock 100 req/min default) from
# tripping with 429s during fast/back-to-back suite runs. All tiers are raised
# so only dedicated rate-limit tests exercise the limits.
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000000"
os.environ["RATE_LIMIT_LLM_PER_MINUTE"] = "1000000"
os.environ["RATE_LIMIT_WIDGET_BOOTSTRAP_PER_MINUTE"] = "1000000"
os.environ["RATE_LIMIT_WIDGET_SESSION_PER_MINUTE"] = "1000000"


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat = AsyncMock()
    provider.stream = AsyncMock()
    provider.embeddings = AsyncMock()
    provider.health_check = AsyncMock()
    provider.list_models = AsyncMock()
    provider.structured_output = AsyncMock()
    provider.tool_call = AsyncMock()
    return provider


@pytest.fixture
def mock_factory(mock_provider):
    factory = MagicMock()
    factory.get_provider.return_value = mock_provider
    return factory


def override_auth_dependencies(app) -> None:
    """Bypass JWT auth for router-logic unit tests (auth itself is covered by
    tests/unit/infrastructure/test_security.py, middleware tests and the
    knowledge auth-guard tests)."""
    from types import SimpleNamespace

    from app.api.auth import dependencies as auth_deps

    store_id = "store-1"
    org_id = "org-1"
    user = SimpleNamespace(user_id="11111111-1111-1111-1111-111111111111")

    app.dependency_overrides.update(
        {
            auth_deps.require_admin_role: lambda: None,
            auth_deps.require_super_admin_role: lambda: None,
            auth_deps.get_current_user: lambda: user,
            auth_deps.get_current_store_id: lambda: store_id,
            auth_deps.get_current_organization_id: lambda: org_id,
            auth_deps.get_optional_organization_id: lambda: org_id,
            auth_deps.get_optional_store_id: lambda: store_id,
        }
    )


def admin_headers(
    role: str = "Admin",
    store_id: str = "22222222-2222-2222-2222-222222222222",
    store_admin_email: str | None = None,
    store_admin_password: str | None = None,
) -> dict[str, str]:
    """Bearer headers using a contract-compliant token for integration tests.

    Mirrors the exact claim set the .NET backend emits (sub + ASP.NET NameIdentifier URI,
    email + emailaddress URI, security_stamp, role URI, store_id, org_id optional).
    Pass ``store_admin_email``/``store_admin_password`` to include the e-commerce
    admin credentials claims used by the integration "Sync Now" flow.
    """
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    from app.core.auth_settings import auth_settings
    from app.core.security import EMAIL_CLAIM, NAME_IDENTIFIER_CLAIM

    user_guid = "11111111-1111-1111-1111-111111111111"
    payload = {
        "sub": user_guid,
        NAME_IDENTIFIER_CLAIM: user_guid,
        "email": "admin@example.com",
        EMAIL_CLAIM: "admin@example.com",
        "security_stamp": "test-security-stamp",
        "store_id": store_id,
        "org_id": "33333333-3333-3333-3333-333333333333",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": role,
        "iss": auth_settings.JWT_ISSUER,
        "aud": auth_settings.JWT_AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }
    if store_admin_email is not None:
        payload["store_admin_email"] = store_admin_email
    if store_admin_password is not None:
        payload["store_admin_password"] = store_admin_password
    token = pyjwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}
