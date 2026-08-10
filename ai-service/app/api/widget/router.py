import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.ai.dependencies import get_conversation_service
from app.api.rag.dependencies import get_rag_service
from app.api.recommendation.dependencies import get_recommendation_service
from app.api.widget.dependencies import (
    get_widget_bootstrap_service,
    get_widget_tenant_context,
    require_widget_scope,
)
from app.api.widget.schemas import (
    WidgetBootstrapResponseSchema,
    WidgetChatRequestSchema,
    WidgetChatResponseSchema,
    WidgetRecommendationRequestSchema,
    WidgetRecommendationResponseSchema,
)
from app.application.rag.dto import RAGRequest
from app.application.rag.service import RagOrchestrationService
from app.application.recommendation.services import RecommendationService
from app.application.services.conversation_service import ConversationService
from app.application.widget.bootstrap_service import WidgetBootstrapService
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationNotFoundError,
    WidgetOriginNotAllowedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget", tags=["Widget"])

WIDGET_KEY_HEADER = "X-Widget-Key"

GENERIC_BOOTSTRAP_ERROR = "Invalid widget key"


@router.post(
    "/bootstrap",
    response_model=WidgetBootstrapResponseSchema,
    summary="Initialize a storefront widget session",
)
async def widget_bootstrap(
    request: Request,
    x_widget_key: str = Header(..., alias=WIDGET_KEY_HEADER, min_length=8),
    bootstrap_service: WidgetBootstrapService = Depends(get_widget_bootstrap_service),
) -> WidgetBootstrapResponseSchema:
    origin = request.headers.get("Origin")
    try:
        session = await bootstrap_service.bootstrap(x_widget_key, origin)
    except (WidgetInstallationNotFoundError, WidgetOriginNotAllowedError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=GENERIC_BOOTSTRAP_ERROR) from exc

    return WidgetBootstrapResponseSchema(
        access_token=session.access_token,
        expires_in=session.expires_in,
        widget_id=session.widget_id,
        configuration=session.configuration,
    )


@router.post(
    "/chat",
    response_model=WidgetChatResponseSchema,
    summary="Widget chat grounded in the store's knowledge base",
    dependencies=[Depends(require_widget_scope("rag:chat"))],
)
async def widget_chat(
    payload: WidgetChatRequestSchema,
    request: Request,
    tenant_context: TenantContext = Depends(get_widget_tenant_context),
    rag_service: RagOrchestrationService = Depends(get_rag_service),
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> WidgetChatResponseSchema:
    if payload.conversation_id:
        owned = await conversation_service.conversation_owned_by_store(
            payload.conversation_id,
            tenant_context.store_id,
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rag_request = RAGRequest(
        message=payload.message,
        conversation_id=payload.conversation_id,
        customer_id=payload.customer_id,
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        use_hybrid=payload.use_hybrid,
        use_mmr=payload.use_mmr,
        rerank=payload.rerank,
        language=payload.language,
        knowledge_scope=payload.knowledge_scope,
        stream=False,
    )
    result = await rag_service.answer(rag_request)

    return WidgetChatResponseSchema(
        response=result.response,
        citations=[c.model_dump() for c in result.citations],
        chunk_references=[r.model_dump() for r in result.chunk_references],
        confidence_score=result.confidence_score,
        latency_ms=result.latency_ms,
        model=result.model,
        provider=result.provider,
        usage=result.usage.model_dump(),
        business_summary_version=result.business_summary_version,
        conversation_id=result.conversation_id,
    )


@router.post(
    "/recommendations",
    response_model=WidgetRecommendationResponseSchema,
    summary="Widget product recommendations scoped to the store",
    dependencies=[Depends(require_widget_scope("recommendations:read"))],
)
async def widget_recommendations(
    payload: WidgetRecommendationRequestSchema,
    request: Request,
    tenant_context: TenantContext = Depends(get_widget_tenant_context),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
) -> WidgetRecommendationResponseSchema:
    result = await recommendation_service.recommend(
        query=payload.message,
        store_id=tenant_context.store_id,
        customer_id=payload.customer_id,
    )

    return WidgetRecommendationResponseSchema(
        query=result.query,
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
        customer_id=result.customer_id,
    )
