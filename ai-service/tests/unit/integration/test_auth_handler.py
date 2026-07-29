import json

import httpx
import pytest

from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation
from app.infrastructure.http.auth.auth_handler import AuthHandler


@pytest.fixture
def handler() -> AuthHandler:
    return AuthHandler()


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient()


class TestAuthHandlerApiKey:
    def test_api_key_header(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.APIKEY, name="X-API-Key")
        creds = json.dumps({"X-API-Key": "my-secret-key"})
        handler.attach_auth(client, auth, creds)
        assert client.headers.get("X-API-Key") == "my-secret-key"

    def test_api_key_query(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(
            type=AuthType.APIKEY,
            credentials_location=CredentialsLocation.QUERY,
            name="api_key",
        )
        handler.attach_auth(client, auth, json.dumps({"api_key": "secret"}))
        assert client.params is not None

    def test_api_key_cookie(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(
            type=AuthType.APIKEY,
            credentials_location=CredentialsLocation.COOKIE,
            name="session",
        )
        handler.attach_auth(client, auth, json.dumps({"session": "token123"}))
        assert client.cookies is not None


class TestAuthHandlerBearer:
    def test_bearer_token(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.BEARER, scheme="bearer")
        creds = json.dumps({"access_token": "my-token"})
        handler.attach_auth(client, auth, creds)
        assert client.headers.get("Authorization") == "Bearer my-token"

    def test_bearer_no_credentials(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.BEARER, scheme="bearer")
        handler.attach_auth(client, auth, None)
        assert client.headers.get("Authorization") is None


class TestAuthHandlerBasic:
    def test_basic_auth(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.BASIC, scheme="basic")
        creds = json.dumps({"username": "admin", "password": "pass123"})
        handler.attach_auth(client, auth, creds)
        auth_header = client.headers.get("Authorization")
        assert auth_header is not None
        assert auth_header.startswith("Basic ")

    def test_basic_missing_credentials(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.BASIC, scheme="basic")
        handler.attach_auth(client, auth, json.dumps({}))
        assert client.headers.get("Authorization") is None


class TestAuthHandlerOAuth2:
    def test_oauth2_bearer(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.OAUTH2, token_url="https://auth.example.com")
        creds = json.dumps({"access_token": "oauth-token"})
        handler.attach_auth(client, auth, creds)
        assert client.headers.get("Authorization") == "Bearer oauth-token"


class TestAuthHandlerEdgeCases:
    def test_invalid_json_credentials(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.APIKEY, name="Key")
        handler.attach_auth(client, auth, "not-json")
        assert client.headers.get("Key") is None

    def test_no_credentials(self, handler: AuthHandler, client: httpx.AsyncClient) -> None:
        auth = AuthConfig(type=AuthType.APIKEY, name="Key")
        handler.attach_auth(client, auth, None)
        assert client.headers.get("Key") is None