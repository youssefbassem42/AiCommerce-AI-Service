import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.admin.dependencies import get_sentiment_analytics_service
from app.api.admin.schemas import SentimentOverviewResponse
from app.api.auth.dependencies import require_super_admin_role
from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin/analytics",
    tags=["Admin Analytics"],
    dependencies=[Depends(require_super_admin_role)],
)


@router.get("/sentiment/overview", response_model=SentimentOverviewResponse)
async def sentiment_overview(
    service: SentimentAnalyticsService = Depends(get_sentiment_analytics_service),
) -> SentimentOverviewResponse:
    try:
        result = await service.get_sentiment_overview()
        return SentimentOverviewResponse(**result)
    except Exception as exc:
        logger.error("Failed to get sentiment overview: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sentiment overview: {exc}",
        )
