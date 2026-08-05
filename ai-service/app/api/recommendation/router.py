import logging

from fastapi import APIRouter, Depends

from app.api.rag.dependencies import get_tenant_context
from app.api.recommendation.dependencies import (
    get_bundle_service,
    get_recommendation_service,
)
from app.api.recommendation.schemas import (
    BundleRequestSchema,
    BundleResponseSchema,
    RecommendationRequestSchema,
    RecommendationResponseSchema,
)
from app.application.recommendation.services import (
    BundleSuggestionService,
    RecommendationService,
)
from app.domain.knowledge.value_objects.tenant_context import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["Recommendations"])


@router.post(
    "/chat",
    response_model=RecommendationResponseSchema,
    summary="AI-powered product recommendation with spec matching",
)
async def recommend_products(
    payload: RecommendationRequestSchema,
    service: RecommendationService = Depends(get_recommendation_service),
    tenant_context: TenantContext | None = Depends(get_tenant_context),
) -> RecommendationResponseSchema:
    store_id = tenant_context.store_id if tenant_context else payload.store_id
    result = await service.recommend(
        query=payload.message,
        store_id=store_id,
        customer_id=payload.customer_id,
    )

    return RecommendationResponseSchema(
        query=result.query,
        store_id=result.store_id,
        customer_id=result.customer_id,
        products=[
            {
                "product_id": p.product_id,
                "title": p.title,
                "price": str(p.price),
                "currency": p.currency,
                "image_url": p.image_url,
                "product_url": p.product_url,
                "specs": [s.model_dump() for s in p.specs],
                "match_reasons": p.match_reasons,
            }
            for p in result.products
        ],
        rationale=result.rationale,
        total_count=result.total_count,
        latency_ms=result.latency_ms,
    )


@router.post(
    "/bundle-suggestion",
    response_model=BundleResponseSchema,
    summary="AI-powered bundle suggestion with budget awareness",
)
async def suggest_bundle(
    payload: BundleRequestSchema,
    service: BundleSuggestionService = Depends(get_bundle_service),
    tenant_context: TenantContext | None = Depends(get_tenant_context),
) -> BundleResponseSchema:
    store_id = tenant_context.store_id if tenant_context else payload.store_id
    result = await service.suggest(
        query=payload.message,
        store_id=store_id,
        customer_id=payload.customer_id,
    )

    return BundleResponseSchema(
        query=result.query,
        store_id=result.store_id,
        customer_id=result.customer_id,
        budget=result.budget,
        bundles=[
            {
                "products": [
                    {
                        "product_id": p.product_id,
                        "product_title": p.product_title,
                        "original_price": str(p.original_price),
                        "discount_pct": p.discount_pct,
                        "discount_amount": str(p.discount_amount),
                        "price_after_discount": str(p.price_after_discount),
                    }
                    for p in b.products
                ],
                "total_original": str(b.total_original),
                "total_discount": str(b.total_discount),
                "total_after_discount": str(b.total_after_discount),
                "remaining_budget": b.remaining_budget,
                "within_budget": b.within_budget,
                "promo_code": b.promo_code,
                "rank": b.rank,
            }
            for b in result.bundles
        ],
        promo_code=result.promo_code,
        rationale=result.rationale,
        latency_ms=result.latency_ms,
    )
