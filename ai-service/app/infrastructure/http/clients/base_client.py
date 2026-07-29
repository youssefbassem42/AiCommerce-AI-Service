import logging
import uuid
from contextvars import ContextVar
from typing import Any, Optional

import httpx

from app.domain.integration.value_objects.auth_config import AuthConfig
from app.infrastructure.http.auth.auth_handler import AuthHandler
from app.infrastructure.http.retry import RetryHandler

logger = logging.getLogger(__name__)

correlation_id_var: ContextVar[str] = ContextVar("_correlation_id", default="")


class ConnectionConfig:
    """Configuration for an external API connection."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        pool_connections: int = 10,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.pool_connections = pool_connections


class ExternalApiClient:
    """Dynamic HTTP client configured from an IntegrationConnection."""

    def __init__(
        self,
        config: ConnectionConfig,
        auth_config: Optional[AuthConfig] = None,
        encrypted_credentials: Optional[str] = None,
        auth_handler: Optional[AuthHandler] = None,
        retry_handler: Optional[RetryHandler] = None,
    ):
        self._config = config
        self._auth_config = auth_config
        self._encrypted_credentials = encrypted_credentials
        self._auth_handler = auth_handler or AuthHandler()
        self._retry_handler = retry_handler or RetryHandler(
            max_retries=config.max_retries,
        )
        self._client = self._build_client()

    def _build_client(self) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=httpx.Timeout(self._config.timeout),
            limits=httpx.Limits(
                max_connections=self._config.pool_connections,
                max_keepalive_connections=self._config.pool_connections,
            ),
            follow_redirects=True,
        )

        if self._auth_config and self._encrypted_credentials:
            self._auth_handler.attach_auth(
                client,
                self._auth_config,
                self._encrypted_credentials,
            )
        else:
            logger.warning("No auth config or credentials provided to client.")

        correlation_id = correlation_id_var.get() or str(uuid.uuid4())
        client.headers["X-Correlation-ID"] = correlation_id

        return client

    async def request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        correlation_id = correlation_id_var.get() or str(uuid.uuid4())
        request_headers = dict(headers or {})
        request_headers.setdefault("X-Correlation-ID", correlation_id)

        logger.info(
            "External API request: %s %s (correlation_id=%s)",
            method.upper(),
            path,
            correlation_id,
        )

        response = await self._retry_handler.execute(
            self._client.request,
            method=method,
            url=path,
            params=params,
            json=body,
            headers=request_headers,
        )

        logger.info(
            "External API response: %s %s -> %d (correlation_id=%s)",
            method.upper(),
            path,
            response.status_code,
            correlation_id,
        )

        if response.status_code == 204:
            return {}
        try:
            return response.json()
        except Exception:
            return {}

    async def get(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self.request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self.request("POST", path, body=body, headers=headers)

    async def put(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self.request("PUT", path, body=body, headers=headers)

    async def patch(
        self,
        path: str,
        body: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self.request("PATCH", path, body=body, headers=headers)

    async def delete(
        self,
        path: str,
        headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self.request("DELETE", path, headers=headers)

    async def close(self) -> None:
        await self._client.aclose()