import base64
import json
import logging
from typing import Optional

import httpx

from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation

logger = logging.getLogger(__name__)


class AuthHandler:
    """Attaches authentication to an httpx client based on AuthConfig."""

    def attach_auth(
        self,
        client: httpx.AsyncClient,
        auth_config: AuthConfig,
        credentials_json: Optional[str] = None,
    ) -> None:
        if not credentials_json:
            logger.warning("No credentials provided for auth type '%s'.", auth_config.type.value)
            return

        try:
            credentials: dict = json.loads(credentials_json)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to decode credentials JSON.")
            return

        if auth_config.type == AuthType.APIKEY:
            self._apply_api_key(client, auth_config, credentials)
        elif auth_config.type == AuthType.BEARER:
            self._apply_bearer(client, credentials)
        elif auth_config.type == AuthType.BASIC:
            self._apply_basic(client, credentials)
        elif auth_config.type == AuthType.OAUTH2:
            self._apply_oauth2(client, credentials)
        else:
            logger.warning("Unsupported auth type: %s", auth_config.type)

    def _apply_api_key(
        self,
        client: httpx.AsyncClient,
        auth_config: AuthConfig,
        credentials: dict,
    ) -> None:
        key_name = auth_config.name or "api_key"
        key_value = credentials.get(key_name) or credentials.get("api_key", "")

        if auth_config.credentials_location == CredentialsLocation.HEADER:
            client.headers[key_name] = key_value
        elif auth_config.credentials_location == CredentialsLocation.QUERY:
            if client.params is None:
                client.params = httpx.QueryParams({key_name: key_value})
            else:
                client.params = client.params.merge({key_name: key_value})
        elif auth_config.credentials_location == CredentialsLocation.COOKIE:
            jar = httpx.Cookies()
            jar.set(key_name, key_value)
            client.cookies = jar
        else:
            client.headers[key_name] = key_value

    def _apply_bearer(
        self,
        client: httpx.AsyncClient,
        credentials: dict,
    ) -> None:
        token = credentials.get("access_token") or credentials.get("token") or ""
        if token:
            client.headers["Authorization"] = f"Bearer {token}"

    def _apply_basic(  # noqa: PLR6301
        self,
        client: httpx.AsyncClient,
        credentials: dict,
    ) -> None:
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if username and password:
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            client.headers["Authorization"] = f"Basic {encoded}"

    def _apply_oauth2(
        self,
        client: httpx.AsyncClient,
        credentials: dict,
    ) -> None:
        token = credentials.get("access_token") or credentials.get("token") or ""
        if token:
            client.headers["Authorization"] = f"Bearer {token}"