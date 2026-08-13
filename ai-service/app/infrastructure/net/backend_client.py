"""Typed HTTP client for the .NET backend (plan/subscription authority).

The .NET service owns subscriptions, plan entitlements and the store's daily
allowed message override. FastAPI is the runtime enforcement authority and
forwards the caller's own Bearer token when calling back into .NET, so .NET's
own role/permission checks apply.

Endpoints consumed:
- ``GET  /api/stores/{store_id}/daily-allowed-message``
- ``POST /api/stores/{store_id}/update-daily-allowed-message``
- ``GET  /api/seller/subscriptions/User-Subscription-plan``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# .NET may send human-readable provider names ("OpenAI", "Gemini" ...) that
# must map onto the registry provider identifiers ("openai", "gemini" ...).
NET_PROVIDER_ALIASES = {
    "openai": "openai",
    "azure": "azure",
    "gemini": "gemini",
    "google": "gemini",
    "claude": "claude",
    "anthropic": "claude",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "ollama": "ollama",
    "openrouter": "openrouter",
}


class NetBackendError(Exception):
    """The .NET backend rejected or could not serve a plan-related call."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class NetDailyAllowedMessage:
    """``GET /api/stores/{store_id}/daily-allowed-message`` payload."""

    daily_allowed_message: int | None = None
    plan_daily_allowed_message: int | None = None
    store_override: int | None = None


@dataclass(frozen=True)
class NetSubscriptionPlan:
    """``GET /api/seller/subscriptions/User-Subscription-plan`` payload."""

    subscription_status: str = ""
    num_of_tokens: int = 0
    renewal_date: str = ""
    ai_models: list[str] = None  # type: ignore[assignment]
    allowed_providers: list[str] = None  # type: ignore[assignment]
    plan_name: str = ""

    def __post_init__(self) -> None:
        if self.ai_models is None:
            object.__setattr__(self, "ai_models", [])
        if self.allowed_providers is None:
            object.__setattr__(self, "allowed_providers", [])


def normalize_provider_names(raw: Any) -> list[str]:
    """Map .NET provider names onto registry provider identifiers."""
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.split(",") if p.strip()]
    if not isinstance(raw, list):
        return []
    normalized: list[str] = []
    for entry in raw:
        key = str(entry or "").strip().lower()
        if not key:
            continue
        provider = NET_PROVIDER_ALIASES.get(key, key)
        if provider not in normalized:
            normalized.append(provider)
    return normalized


class NetBackendClient:
    """Small typed client for the .NET plan/subscription endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (base_url or settings.NET_BACKEND_BASE_URL).rstrip("/")
        self._timeout = timeout or settings.NET_BACKEND_TIMEOUT_SECONDS
        self._max_retries = max_retries if max_retries is not None else settings.NET_BACKEND_MAX_RETRIES
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            transport=transport,
        )

    async def get_daily_allowed_message(self, store_id: str, token: str) -> NetDailyAllowedMessage:
        data = await self._request("GET", f"/api/stores/{store_id}/daily-allowed-message", token=token)
        return NetDailyAllowedMessage(
            daily_allowed_message=_to_int(data.get("dailyAllowedMessage")),
            plan_daily_allowed_message=_to_int(data.get("planDailyAllowedMessage")),
            store_override=_to_int(data.get("storeOverride")),
        )

    async def update_daily_allowed_message(self, store_id: str, value: int, token: str) -> None:
        await self._request(
            "POST",
            f"/api/stores/{store_id}/update-daily-allowed-message",
            token=token,
            body={"dailyAllowedMessage": value},
        )

    async def get_subscription_plan(self, token: str) -> NetSubscriptionPlan:
        data = await self._request("GET", "/api/seller/subscriptions/User-Subscription-plan", token=token)
        return NetSubscriptionPlan(
            subscription_status=str(data.get("subscriptionStatus") or ""),
            num_of_tokens=_to_int(data.get("numOfTokens")) or 0,
            renewal_date=str(data.get("renewalDate") or ""),
            ai_models=_as_string_list(data.get("aiModels")),
            allowed_providers=normalize_provider_names(data.get("allowedProviders")),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        token: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        last_error: Exception | None = None
        attempts = self._max_retries + 1 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = await self._client.request(
                    method,
                    path,
                    json=body,
                    headers=headers,
                )
                if response.status_code < 200 or response.status_code >= 300:
                    raise NetBackendError(
                        f".NET backend {method} {path} -> {response.status_code}: {response.text[:200]}",
                        status_code=response.status_code,
                    )
                try:
                    return response.json()
                except Exception:
                    return {}
            except NetBackendError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Net backend request failed (%s %s, attempt %d/%d): %s",
                    method,
                    path,
                    attempt + 1,
                    attempts,
                    exc,
                )
                if attempt + 1 == attempts:
                    break
        raise NetBackendError(f".NET backend unreachable: {last_error}") from last_error


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


net_backend_client = NetBackendClient()
