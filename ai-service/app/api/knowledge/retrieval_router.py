import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.auth.dependencies import get_current_user
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.knowledge.retrieval_schemas import RetrievalRequestSchema, RetrievalResponseSchema, RetrievedChunkSchema
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.core.security import ERR_NO_ORG, ERR_NO_STORE

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/knowledge/retrieval",
    tags=["Knowledge Retrieval"],
    dependencies=[Depends(get_current_user)],
)


def _resolve_filters(payload: RetrievalRequestSchema, request: Request) -> RetrievalFilters:
    """Tenant filters come from validated JWT claims ONLY.

    `payload.store_id` / `payload.organization_id` remain in the request contract
    for backward compatibility but are deliberately IGNORED — server-derived tenant
    identity is authoritative. An authenticated request without a store/organization
    claim is denied instead of falling back to client-supplied identifiers.
    """
    store_id = getattr(request.state, "store_id", None)
    organization_id = getattr(request.state, "organization_id", None)
    if not store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_STORE)
    if not organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_ORG)
    if payload.store_id and payload.store_id != store_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_STORE)
    if payload.organization_id and payload.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERR_NO_ORG)
    return RetrievalFilters(
        organization_id=organization_id,
        store_id=store_id,
        language=payload.language,
        document_type=payload.document_type,
        knowledge_scope=payload.knowledge_scope,
        business_version=payload.business_version,
    )


@router.post("/search", response_model=RetrievalResponseSchema)
async def search(
    payload: RetrievalRequestSchema,
    request: Request,
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    config = RetrievalConfig(
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        use_hybrid=payload.use_hybrid,
        use_mmr=payload.use_mmr,
        mmr_lambda=payload.mmr_lambda,
        rerank=payload.rerank,
        rerank_top_k=payload.rerank_top_k,
        embedding_model=payload.embedding_model,
    )

    filters = _resolve_filters(payload, request)

    result = await service.search(
        query=payload.query,
        filters=filters,
        config=config,
    )

    return RetrievalResponseSchema(
        query=result.query,
        results=[RetrievedChunkSchema(**dto.model_dump()) for dto in result.results],
        total_count=result.total_count,
        strategy=result.strategy,
        latency_ms=result.latency_ms,
        filters_applied=result.filters_applied,
    )
