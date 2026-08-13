import logging

from fastapi import HTTPException, Request, status

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService
from app.infrastructure.net.backend_client import NetBackendClient

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"admin", "store_admin"}

_net_backend_client: NetBackendClient | None = None


def get_net_backend_client() -> NetBackendClient:
    """Shared .NET backend client (created once; httpx connections reused)."""
    global _net_backend_client  # noqa: PLW0603
    if _net_backend_client is None:
        _net_backend_client = NetBackendClient()
    return _net_backend_client


def get_bearer_token(request: Request) -> str:
    """Extract the raw Bearer token so it can be forwarded to .NET."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


async def require_admin_role(request: Request) -> None:
    roles = getattr(request.state, "roles", [])
    if not roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: no roles assigned",
        )
    if "super_admin" in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: super admins cannot access store-level analytics",
        )
    if not any(r in ADMIN_ROLES for r in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: requires admin role",
        )


def get_sentiment_analytics_service() -> SentimentAnalyticsService:
    return SentimentAnalyticsService()
