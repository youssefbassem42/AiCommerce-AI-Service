import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.rag.dependencies import get_rag_service, get_tenant_context
from app.api.rag.schemas import RAGChatRequestSchema, RAGChatResponseSchema
from app.application.rag.dto import RAGRequest
from app.application.rag.service import RagOrchestrationService
from app.domain.knowledge.value_objects.tenant_context import TenantContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Chat"])


def _resolve_rag_request(
    payload: RAGChatRequestSchema,
    tenant_context: TenantContext | None,
) -> RAGRequest:
    data = payload.model_dump()
    if tenant_context:
        data["store_id"] = tenant_context.store_id
        data["organization_id"] = tenant_context.organization_id
    return RAGRequest(**data)


@router.post("/chat", response_model=RAGChatResponseSchema)
async def rag_chat(
    payload: RAGChatRequestSchema,
    request: Request,
    service: RagOrchestrationService = Depends(get_rag_service),
    tenant_context: TenantContext | None = Depends(get_tenant_context),
) -> RAGChatResponseSchema:
    rag_request = _resolve_rag_request(payload, tenant_context)
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
@router.post("/chat/stream")
async def rag_chat_stream(
    payload: RAGChatRequestSchema,
    request: Request,
    service: RagOrchestrationService = Depends(get_rag_service),
    tenant_context: TenantContext | None = Depends(get_tenant_context),
) -> StreamingResponse:
    rag_request = _resolve_rag_request(payload, tenant_context)

    async def event_generator():
        async for chunk in service.answer_stream(rag_request):
            yield f"data: {chunk.model_dump_json()}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
