from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.application.integration.auth.authenticator import (
    DEFAULT_MAX_ATTEMPTS,
    EcommerceAuthenticator,
    discover_login_endpoint,
    resolve_api_base_url,
)
from app.domain.integration.exceptions import IntegrationAuthenticationError

SPEC_WITH_LOGIN = {
    "openapi": "3.0.3",
    "servers": [{"url": "https://93.184.216.34"}],
    "paths": {
        "/api/Auth/login": {
            "post": {
                "summary": "Login user and obtain JWT token",
                "responses": {"200": {"description": "Login successful"}},
            }
        },
        "/api/Products": {
            "get": {
                "summary": "Get list of products",
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}

SPEC_LOGIN_IN_OPERATION_ID = {
    "servers": [{"url": "https://93.184.216.34"}],
    "paths": {
        "/api/session": {
            "post": {
                "operationId": "loginUser",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}

SPEC_WITHOUT_LOGIN = {
    "servers": [{"url": "https://93.184.216.34"}],
    "paths": {
        "/api/Products": {
            "get": {"responses": {"200": {"description": "OK"}}}
        }
    },
}


class TestDiscoverLoginEndpoint:
    def test_finds_auth_login_path(self) -> None:
        assert discover_login_endpoint(SPEC_WITH_LOGIN) == "/api/Auth/login"

    def test_finds_login_via_operation_id(self) -> None:
        assert discover_login_endpoint(SPEC_LOGIN_IN_OPERATION_ID) == "/api/session"

    def test_no_login_endpoint(self) -> None:
        assert discover_login_endpoint(SPEC_WITHOUT_LOGIN) is None

    def test_invalid_spec(self) -> None:
        assert discover_login_endpoint({}) is None
        assert discover_login_endpoint(None) is None


class TestResolveApiBaseUrl:
    def test_returns_first_safe_server(self) -> None:
        assert resolve_api_base_url(SPEC_WITH_LOGIN) == "https://93.184.216.34"

    def test_rejects_unsafe_servers(self) -> None:
        spec = {"servers": [{"url": "http://169.254.169.254"}, {"url": "https://93.184.216.34"}]}
        assert resolve_api_base_url(spec) == "https://93.184.216.34"

    def test_no_servers(self) -> None:
        assert resolve_api_base_url({"paths": {}}) is None


class TestEcommerceAuthenticator:
    @pytest.fixture
    def mock_client(self):
        with patch("app.application.integration.auth.authenticator.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            mock_cls.return_value = client
            yield client

    async def test_login_success_returns_token(self, mock_client) -> None:
        mock_client.post = AsyncMock(
            return_value=httpx.Response(200, json={"isSuccess": True, "token": "tok-123"})
        )
        authenticator = EcommerceAuthenticator(max_attempts=DEFAULT_MAX_ATTEMPTS)
        token = await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "Test@123")
        assert token == "tok-123"
        mock_client.post.assert_awaited_once_with(
            "/api/Auth/login",
            json={"email": "admin@example.com", "password": "Test@123"},
        )

    async def test_login_token_nested_in_data(self, mock_client) -> None:
        mock_client.post = AsyncMock(return_value=httpx.Response(200, json={"data": {"token": "nested-tok"}}))
        authenticator = EcommerceAuthenticator(max_attempts=DEFAULT_MAX_ATTEMPTS)
        token = await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "Test@123")
        assert token == "nested-tok"

    async def test_login_fails_after_all_attempts(self, mock_client) -> None:
        mock_client.post = AsyncMock(
            return_value=httpx.Response(401, json={"message": "Invalid credentials"})
        )
        authenticator = EcommerceAuthenticator(max_attempts=3)
        with pytest.raises(IntegrationAuthenticationError) as exc_info:
            await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "wrong")
        assert "3 attempts" in str(exc_info.value)
        assert mock_client.post.await_count == 3

    async def test_login_retries_same_credentials(self, mock_client) -> None:
        responses = [
            httpx.Response(500, json={"message": "server error"}),
            httpx.Response(500, json={"message": "server error"}),
            httpx.Response(200, json={"token": "tok-ok"}),
        ]
        mock_client.post = AsyncMock(side_effect=responses)
        authenticator = EcommerceAuthenticator(max_attempts=3)
        token = await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "Test@123")
        assert token == "tok-ok"
        calls = [call.kwargs["json"] for call in mock_client.post.await_args_list]
        assert all(call == {"email": "admin@example.com", "password": "Test@123"} for call in calls)

    async def test_login_transport_error_retried(self, mock_client) -> None:
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        authenticator = EcommerceAuthenticator(max_attempts=3)
        with pytest.raises(IntegrationAuthenticationError):
            await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "Test@123")
        assert mock_client.post.await_count == 3

    async def test_login_missing_base_url(self, mock_client) -> None:
        authenticator = EcommerceAuthenticator(max_attempts=3)
        with pytest.raises(IntegrationAuthenticationError, match="no base URL"):
            await authenticator.login({"paths": {}}, "admin@example.com", "Test@123")

    async def test_login_missing_login_endpoint(self, mock_client) -> None:
        authenticator = EcommerceAuthenticator(max_attempts=3)
        with pytest.raises(IntegrationAuthenticationError, match="no login endpoint"):
            await authenticator.login(SPEC_WITHOUT_LOGIN, "admin@example.com", "Test@123")

    async def test_client_closed_after_login(self, mock_client) -> None:
        mock_client.post = AsyncMock(return_value=httpx.Response(200, json={"token": "tok"}))
        authenticator = EcommerceAuthenticator(max_attempts=3)
        await authenticator.login(SPEC_WITH_LOGIN, "admin@example.com", "Test@123")
        mock_client.aclose.assert_awaited_once()
