"""E-commerce authentication for the integration "Sync Now" flow.

Credentials come from the AI Commerce JWT (``store_admin_email`` /
``store_admin_password`` claims) — never from the request body and never
persisted. The login endpoint is discovered from the submitted OpenAPI spec,
never assumed, and every login is attempted up to ``max_attempts`` times with
the same credentials before failing.
"""

import logging
from typing import Any

import httpx

from app.domain.integration.exceptions import IntegrationAuthenticationError
from app.infrastructure.http.ssrf import assert_safe_http_url, prevent_ssrf

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30.0

_TOKEN_KEYS = ("token", "access_token", "id_token")
_BODY_TOKEN_KEYS = ("token", "access_token")


def discover_login_endpoint(spec: dict) -> str | None:
    """Locate the e-commerce login endpoint inside the OpenAPI spec.

    Matches POST operations whose path or operationId mentions ``login``,
    preferring paths with an ``auth`` segment (e.g. ``/api/Auth/login``).
    Returns ``None`` when the spec exposes no login endpoint.
    """
    paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
    candidates: list[str] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() != "post" or not isinstance(operation, dict):
                continue
            path_lower = path.lower()
            operation_id = str(operation.get("operationId") or "").lower()
            summary = str(operation.get("summary") or "").lower()
            if "login" in path_lower or "login" in operation_id or "login" in summary:
                candidates.append(path)
    if not candidates:
        return None
    auth_segment = [p for p in candidates if "auth" in p.lower()]
    return auth_segment[0] if auth_segment else candidates[0]


def resolve_api_base_url(spec: dict) -> str | None:
    """Base URL from the spec's ``servers`` (first safe entry), else ``None``."""
    servers = spec.get("servers", []) if isinstance(spec, dict) else []
    if not servers:
        return None
    for entry in servers:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not url:
            continue
        try:
            assert_safe_http_url(url)
        except Exception:
            logger.warning("Skipping unsafe base URL candidate '%s'", url)
            continue
        return url.rstrip("/")
    return None


class EcommerceAuthenticator:
    """Logs into the e-commerce API with the JWT-supplied admin credentials."""

    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS, timeout: float = DEFAULT_TIMEOUT):
        self._max_attempts = max_attempts
        self._timeout = timeout

    async def login(self, spec: dict, email: str, password: str) -> str:
        """Attempt e-commerce login up to ``max_attempts`` times.

        Returns the e-commerce access token on success. The token is meant for
        a single operation and MUST NOT be persisted by the caller. Raises
        ``IntegrationAuthenticationError`` (HTTP 401) after all attempts fail.
        """
        base_url = resolve_api_base_url(spec)
        if not base_url:
            raise IntegrationAuthenticationError(
                "E-commerce authentication failed: no base URL found in the API specification."
            )
        login_path = discover_login_endpoint(spec)
        if not login_path:
            raise IntegrationAuthenticationError(
                "E-commerce authentication failed: no login endpoint was discovered "
                "in the API specification."
            )

        client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            event_hooks={"request": [prevent_ssrf]},
        )
        try:
            return await self._attempt_login(client, login_path, email, password)
        finally:
            await client.aclose()

    async def _attempt_login(
        self,
        client: httpx.AsyncClient,
        login_path: str,
        email: str,
        password: str,
    ) -> str:
        last_reason = "no response"
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await client.post(
                    login_path,
                    json={"email": email, "password": password},
                )
                token = self._extract_token(response)
                if token:
                    logger.info(
                        "E-commerce login succeeded on attempt %d/%d (%s).",
                        attempt,
                        self._max_attempts,
                        login_path,
                    )
                    return token
                last_reason = self._failure_reason(response)
                logger.warning(
                    "E-commerce login attempt %d/%d failed: %s",
                    attempt,
                    self._max_attempts,
                    last_reason,
                )
            except httpx.HTTPError as e:
                last_reason = f"network error: {e}"
                logger.warning(
                    "E-commerce login attempt %d/%d failed: %s",
                    attempt,
                    self._max_attempts,
                    last_reason,
                )

        raise IntegrationAuthenticationError(
            f"E-commerce authentication failed after {self._max_attempts} attempts "
            f"({last_reason}). Check the e-commerce admin panel email and password."
        )

    @staticmethod
    def _extract_token(response: httpx.Response) -> str | None:
        if response.status_code < 200 or response.status_code >= 300:
            return None
        try:
            body: Any = response.json()
        except Exception:
            return None
        if isinstance(body, dict):
            for key in _TOKEN_KEYS:
                value = body.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            nested = body.get("data")
            if isinstance(nested, dict):
                for key in _BODY_TOKEN_KEYS:
                    value = nested.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        return None

    @staticmethod
    def _failure_reason(response: httpx.Response) -> str:
        try:
            body: Any = response.json()
        except Exception:
            return f"HTTP {response.status_code}"
        if isinstance(body, dict):
            message = body.get("message")
            if isinstance(message, str) and message.strip():
                return f"HTTP {response.status_code}: {message.strip()}"
        return f"HTTP {response.status_code}"
