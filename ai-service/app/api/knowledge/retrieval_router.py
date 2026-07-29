import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.knowledge.retrieval_schemas import RetrievalRequestSchema, RetrievalResponseSchema, RetrievedChunkSchema
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge/retrieval", tags=["Knowledge Retrieval"])


@router.post("/search", response_model=RetrievalResponseSchema)
async def search(
    payload: RetrievalRequestSchema,
    service: RetrieverService = Depends(get_retriever_service),
) -> RetrievalResponseSchema:
    try:
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

        filters = RetrievalFilters(
            organization_id=payload.organization_id,
            store_id=payload.store_id,
            language=payload.language,
            document_type=payload.document_type,
            knowledge_scope=payload.knowledge_scope,
            business_version=payload.business_version,
        )

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
    except Exception as exc:
        logger.error("Retrieval search failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {exc}",
        )
