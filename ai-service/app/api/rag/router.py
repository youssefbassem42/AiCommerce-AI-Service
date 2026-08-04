import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.rag.dependencies import get_rag_service
from app.api.rag.schemas import RAGChatRequestSchema, RAGChatResponseSchema
from app.application.rag.dto import RAGRequest
from app.application.rag.service import RagOrchestrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Chat"])


def _resolve_rag_request(payload: RAGChatRequestSchema, request: Request) -> RAGRequest:
    data = payload.model_dump()
    store_id = getattr(request.state, "store_id", None)
    organization_id = getattr(request.state, "organization_id", None)
    if store_id:
        data["store_id"] = store_id
    if organization_id:
        data["organization_id"] = organization_id
    return RAGRequest(**data)


@router.post("/chat", response_model=RAGChatResponseSchema)
async def rag_chat(
    payload: RAGChatRequestSchema,
    request: Request,
    service: RagOrchestrationService = Depends(get_rag_service),
) -> RAGChatResponseSchema:
    try:
        rag_request = _resolve_rag_request(payload, request)
        result = await service.answer(rag_request)

        return RAGChatResponseSchema(
            response=result.response,
            citations=[s.model_dump() for s in result.citations],
            chunk_references=[r.model_dump() for r in result.chunk_references],
            confidence_score=result.confidence_score,
            latency_ms=result.latency_ms,
            model=result.model,
            provider=result.provider,
            usage=result.usage.model_dump(),
            business_summary_version=result.business_summary_version,
            conversation_id=result.conversation_id,
        )
    except Exception as exc:
        logger.error("RAG chat failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG chat failed: {exc}",
        )


@router.post("/chat/stream")
async def rag_chat_stream(
    payload: RAGChatRequestSchema,
    request: Request,
    service: RagOrchestrationService = Depends(get_rag_service),
) -> StreamingResponse:
    try:
        rag_request = _resolve_rag_request(payload, request)

        async def event_generator():
            async for chunk in service.answer_stream(rag_request):
                yield f"data: {chunk.model_dump_json()}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as exc:
        logger.error("RAG stream failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG stream failed: {exc}",
        )
