import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.analytics.dependencies import get_sentiment_analytics_service, require_admin_role
from app.api.analytics.schemas import SentimentSummaryResponse
from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_admin_role)],
)


@router.get(
    "/sentiment-summary",
    response_model=SentimentSummaryResponse,
    summary="Get sentiment breakdown for store tickets (admin only)",
)
async def get_sentiment_summary(
    store_id: str = Query(..., description="Store identifier"),
    service: SentimentAnalyticsService = Depends(get_sentiment_analytics_service),
) -> SentimentSummaryResponse:
    try:
        result = await service.get_sentiment_summary(store_id)
        return SentimentSummaryResponse(**result.model_dump())
    except Exception as exc:
        logger.error("Failed to get sentiment summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sentiment summary: {exc}",
        )
