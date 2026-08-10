import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.analytics.dependencies import get_sentiment_analytics_service, require_admin_role
from app.api.analytics.schemas import SentimentSummaryResponse
from app.api.auth.dependencies import get_current_store_id
from app.application.analytics.sentiment_analytics_service import SentimentAnalyticsService
from app.core.security import ERR_NO_STORE

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
    service: SentimentAnalyticsService = Depends(get_sentiment_analytics_service),
    claimed_store_id: str = Depends(get_current_store_id),
    store_id: str | None = Query(
        default=None,
        description=("Store identifier; if provided it MUST match the authenticated user's store claim"),
    ),
) -> SentimentSummaryResponse:
    """Cross-store protection: the store is resolved from the validated JWT claim.

    A client-supplied `store_id` that does not match the claim is a tenant
    manipulation attempt and is denied — analytics data is store-scoped.
    """
    if store_id and store_id != claimed_store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERR_NO_STORE,
        )
    try:
        result = await service.get_sentiment_summary(claimed_store_id)
        return SentimentSummaryResponse(**result.model_dump())
    except Exception as exc:
        logger.error("Failed to get sentiment summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sentiment summary: {exc}",
        )
