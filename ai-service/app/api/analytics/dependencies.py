import logging

from fastapi import HTTPException, Request, status

from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService

logger = logging.getLogger(__name__)

ADMIN_ROLES = {"admin", "store_admin"}


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
