import logging
import re
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.agents.coordinator.agent import EXECUTABLE_INTENTS
from app.api.ai.dependencies import get_conversation_service, get_orchestration_service
from app.api.knowledge.retrieval_dependencies import get_retriever_service
from app.api.quota.dependencies import get_quota_enforcer
from app.api.rag.dependencies import get_summary_repository
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
from app.application.dto.ai_dto import MessageDTO, UsageDTO
from app.application.knowledge.retrieval import RetrieverService
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.quota.enforcer import QuotaEnforcer
from app.application.rag.dedup import deduplicate_chunks
from app.application.rag.dto import ChunkReference, Citation
from app.application.rag.prompt import BUSINESS_SUMMARY_HEADER, CHUNK_HEADER
from app.application.rag.service import MAX_CHUNKS_IN_CONTEXT
from app.application.recommendation.services import RecommendationService
from app.application.services.conversation_service import ConversationService
from app.application.services.orchestration_service import OrchestrationService
from app.application.widget.bootstrap_service import WidgetBootstrapService
from app.application.widget.policy import apply_widget_policy, widget_policy_from_plan
from app.domain.knowledge.repositories.business_summary_repository import BusinessSummaryRepository
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationNotFoundError,
    WidgetOriginNotAllowedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget", tags=["Widget"])

WIDGET_KEY_HEADER = "X-Widget-Key"

GENERIC_BOOTSTRAP_ERROR = "Invalid widget key"

WIDGET_CONTEXT_HEADER = (
    "You are a helpful e-commerce assistant. Use the store context below to answer "
    "knowledge and policy questions accurately. For casual chat or topics not covered "
    "by the context, respond naturally and helpfully without inventing facts."
)


def _extract_citations(
    text: str,
    chunks: list,
) -> list[Citation]:
    """Extract [citation:N] references from the assistant text (mirrors rag/service.py)."""
    citations: list[Citation] = []
    seen: set[int] = set()

    for match in re.finditer(r"\[citation:\s*(\d+)\]", text):
        idx = int(match.group(1))
        if idx in seen:
            continue
        seen.add(idx)

        if 1 <= idx <= len(chunks):
            c = chunks[idx - 1]
            citations.append(
                Citation(
                    index=idx,
                    chunk_id=c.chunk_id,
                    document_title=c.document_title,
                    content_snippet=c.content[:200],
                    score=c.score,
                    rank=c.rank,
                )
            )

    return citations


def _widget_confidence_score(
    intent: str | None,
    chunks: list,
    has_business_summary: bool,
) -> float:
    """1.0 for agent-handled intents; otherwise retrieval-driven (mirrors rag/service.py)."""
    if intent in EXECUTABLE_INTENTS:
        return 1.0

    if not chunks:
        return 0.0

    top_k = min(5, len(chunks))
    avg_score = sum(c.score for c in chunks[:top_k]) / top_k

    confidence = 0.3 + 0.7 * avg_score if has_business_summary else 0.2 + 0.8 * avg_score

    return max(0.0, min(1.0, confidence))


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
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
    retriever_service: RetrieverService = Depends(get_retriever_service),
    summary_repository: BusinessSummaryRepository = Depends(get_summary_repository),
    conversation_service: ConversationService = Depends(get_conversation_service),
    enforcer: QuotaEnforcer = Depends(get_quota_enforcer),
    provider_name: str | None = Query(default=None, description="Deprecated provider override (server-controlled)"),
) -> WidgetChatResponseSchema:
    if payload.conversation_id:
        owned = await conversation_service.conversation_owned_by_store(
            payload.conversation_id,
            tenant_context.store_id,
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    plan = await enforcer.resolve_plan(tenant_context.store_id)
    policy_result = apply_widget_policy(payload, widget_policy_from_plan(plan))
    if policy_result.clamped:
        logger.warning(
            "Widget chat controls clamped by server policy (store=%s widget=%s): %s",
            tenant_context.store_id,
            getattr(request.state, "widget_id", "?"),
            ", ".join(policy_result.clamped),
        )

    widget_id = getattr(request.state, "widget_id", "")

    conversation_id = payload.conversation_id or str(uuid.uuid4())
    if not payload.conversation_id:
        await conversation_service.get_or_create_conversation(
            conversation_id,
            provider="orchestration",
            model=policy_result.model,
            metadata={"widget_id": widget_id, "path": "widget.chat"},
            store_id=tenant_context.store_id,
        )

    retrieval = await retriever_service.search(
        query=payload.message,
        filters=RetrievalFilters(
            organization_id=tenant_context.organization_id,
            store_id=tenant_context.store_id,
            language=payload.language,
            knowledge_scope=policy_result.knowledge_scope,
        ),
        config=RetrievalConfig(
            top_k=min(policy_result.top_k, MAX_CHUNKS_IN_CONTEXT),
            score_threshold=policy_result.score_threshold,
            use_hybrid=policy_result.use_hybrid,
            use_mmr=policy_result.use_mmr,
            rerank=policy_result.rerank,
        ),
    )
    chunks = deduplicate_chunks(retrieval.results)

    summaries = await summary_repository.find_by_document_id(tenant_context.store_id)
    latest_summary = summaries[0] if summaries else None

    context_message: dict[str, str] | None = None
    if chunks or latest_summary:
        parts = [WIDGET_CONTEXT_HEADER]
        if latest_summary:
            parts.append(
                BUSINESS_SUMMARY_HEADER.format(
                    version=latest_summary.version_number,
                    summary=latest_summary.summary,
                )
            )
        for i, c in enumerate(chunks[:MAX_CHUNKS_IN_CONTEXT], start=1):
            parts.append(
                CHUNK_HEADER.format(
                    index=i,
                    title=c.document_title,
                    content=c.content[:2000],
                )
            )
        context_message = {"role": "system", "content": "\n".join(parts)}

    history: list[dict[str, str]] = []
    if payload.conversation_id:
        history_messages = await conversation_service.get_conversation_history(
            payload.conversation_id,
            store_id=tenant_context.store_id,
        )
        history = [
            {
                "role": m.role,
                "content": m.content if isinstance(m.content, str) else str(m.content),
            }
            for m in history_messages
        ]
    if context_message:
        history = [context_message] + history

    widget_session_id = getattr(request.state, "widget_session_id", "")

    async def execute():
        start_time = time.perf_counter()
        response = await orchestration_service.chat(
            user_input=payload.message,
            store_id=tenant_context.store_id,
            customer_id=payload.customer_id,
            conversation_id=conversation_id,
            history=history,
            metadata={"widget_id": widget_id, "session_id": widget_session_id, "path": "widget.chat"},
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        await conversation_service.save_interaction(
            conversation_id=conversation_id,
            user_message=MessageDTO(role="user", content=payload.message),
            assistant_message=response.message,
            usage=response.usage,
            latency_ms=latency_ms,
            store_id=tenant_context.store_id,
        )
        return response, response.usage

    result, _usage = await enforcer.run(
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        session_id=widget_session_id,
        conversation_id=conversation_id,
        echo_text=payload.message,
        model=policy_result.model,
        max_output_tokens=policy_result.max_tokens,
        request_metadata={"widget_id": widget_id, "path": "widget.chat"},
        execute=execute,
    )

    intent = (result.metadata or {}).get("intent")
    answer_text = result.message.content if isinstance(result.message.content, str) else str(result.message.content)

    return WidgetChatResponseSchema(
        response=answer_text,
        citations=[c.model_dump() for c in _extract_citations(answer_text, chunks)],
        chunk_references=[
            ChunkReference(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                content_snippet=c.content[:200],
                score=c.score,
                rank=c.rank,
            ).model_dump()
            for c in chunks
        ],
        confidence_score=_widget_confidence_score(intent, chunks, latest_summary is not None),
        latency_ms=result.latency_ms,
        model=result.model,
        provider=result.provider,
        usage=result.usage.model_dump() if result.usage else UsageDTO().model_dump(),
        business_summary_version=latest_summary.version_number if latest_summary else None,
        conversation_id=conversation_id,
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
    enforcer: QuotaEnforcer = Depends(get_quota_enforcer),
) -> WidgetRecommendationResponseSchema:
    plan = await enforcer.resolve_plan(tenant_context.store_id)

    async def execute():
        result = await recommendation_service.recommend(
            query=payload.message,
            store_id=tenant_context.store_id,
            customer_id=payload.customer_id,
        )
        return result, None

    result, _usage = await enforcer.run(
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        session_id=getattr(request.state, "widget_session_id", ""),
        conversation_id="",
        echo_text=payload.message,
        model=plan.fallback_model,
        request_metadata={"widget_id": getattr(request.state, "widget_id", ""), "path": "widget.recommendations"},
        execute=execute,
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
