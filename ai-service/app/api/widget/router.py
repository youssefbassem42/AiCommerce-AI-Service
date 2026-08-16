import logging
import re
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.agents.coordinator.agent import EXECUTABLE_INTENTS
from app.api.ai.dependencies import get_conversation_service, get_orchestration_service
from app.api.quota.dependencies import get_quota_enforcer
from app.api.recommendation.dependencies import get_recommendation_service
from app.api.widget.conversation_gate import (
    ESCALATION_REPLY,
    GREETING_REPLY,
    GateCategory,
    classify_widget_message,
    contains_internal_leak,
    scrub_internal_labels,
)
from app.api.widget.dependencies import (
    get_context_builder,
    get_widget_bootstrap_service,
    get_widget_tenant_context,
    require_widget_scope,
)
from app.api.widget.schemas import (
    WidgetBootstrapResponseSchema,
    WidgetBundleEventRequestSchema,
    WidgetBundleEventResponseSchema,
    WidgetChatRequestSchema,
    WidgetChatResponseSchema,
    WidgetRecommendationRequestSchema,
    WidgetRecommendationResponseSchema,
)
from app.application.analytics.bundle_tracking_service import BundleTrackingService
from app.application.context.builder import ContextBuilder
from app.application.contracts.bundle import BundlePayload
from app.application.contracts.product import ProductPayload
from app.application.dto.ai_dto import ChatResponse, MessageDTO, UsageDTO
from app.application.quota.enforcer import QuotaEnforcer
from app.application.rag.dedup import deduplicate_chunks
from app.application.rag.dto import ChunkReference, Citation
from app.application.rag.service import MAX_CHUNKS_IN_CONTEXT
from app.application.recommendation.services import RecommendationService
from app.application.services.conversation_service import ConversationService
from app.application.services.orchestration_service import OrchestrationService
from app.application.widget.bootstrap_service import WidgetBootstrapService
from app.application.widget.policy import apply_widget_policy, widget_policy_from_plan
from app.core.ai_logging import log_flow_event
from app.core.request_context import get_request_id
from app.domain.knowledge.value_objects.tenant_context import TenantContext
from app.domain.widget.repositories.widget_installation_repository import (
    WidgetInstallationNotFoundError,
    WidgetOriginNotAllowedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget", tags=["Widget"])

WIDGET_KEY_HEADER = "X-Widget-Key"

GENERIC_BOOTSTRAP_ERROR = "Invalid widget key"


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


def _canned_chat_response(
    reply: str,
    model: str,
    response_type: str = "text",
    widget_block: dict | None = None,
    sub_agent: str | None = None,
) -> ChatResponse:
    """Build a ChatResponse for gate short-circuits and canned outcomes."""
    return ChatResponse(
        id=str(uuid.uuid4()),
        model=model,
        provider="orchestration",
        message=MessageDTO(role="assistant", content=reply),
        usage=UsageDTO(),
        latency_ms=0.0,
        metadata={
            "intent": None,
            "sub_agent": sub_agent,
            "needs_clarification": False,
            "widget": {"type": response_type, **(widget_block or {})},
        },
    )


def _log_widget_chat_complete(
    message_id: str,
    *,
    store_id: str | None,
    conversation_id: str | None,
    response_type: str,
    gate: str | None = None,
    product_count: int = 0,
    bundle_present: bool = False,
    promo_code_present: bool = False,
    escalation: bool = False,
    model: str | None = None,
    provider: str | None = None,
    latency_ms: float = 0.0,
) -> None:
    log_flow_event(
        "widget.chat.complete",
        message_id=message_id,
        store_id=store_id,
        conversation_id=conversation_id,
        response_type=response_type,
        gate=gate,
        product_count=product_count,
        bundle_present=bundle_present,
        promo_code_present=promo_code_present,
        escalation=escalation,
        model=model,
        provider=provider,
        latency_ms=latency_ms,
    )


async def _track_bundle_events(
    *,
    store_id: str,
    bundle: dict | None,
    conversation_id: str | None = None,
    customer_id: str | None = None,
) -> None:
    """Record bundle_shown / promo_displayed (Fix 5.6).

    Analytics failures never break the chat response.
    """
    if not bundle:
        return
    try:
        items = bundle.get("items") or []
        product_ids = [
            str(item.get("product_id")) for item in items if isinstance(item, dict) and item.get("product_id")
        ]
        promo_code = bundle.get("promo_code")

        await BundleTrackingService().track_event(
            store_id=store_id,
            event="bundle_shown",
            conversation_id=conversation_id,
            customer_id=customer_id,
            product_ids=product_ids,
            promo_code=promo_code,
        )
        if promo_code:
            await BundleTrackingService().track_event(
                store_id=store_id,
                event="promo_displayed",
                conversation_id=conversation_id,
                customer_id=customer_id,
                product_ids=product_ids,
                promo_code=promo_code,
            )
    except Exception as exc:  # pragma: no cover - defensive; analytics is best-effort
        logger.warning("Failed to record bundle_shown for store %s: %s", store_id, exc)


_ORDINAL_INDEX = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
}

_FOLLOW_UP_SHOW_ALL_RE = re.compile(r"\bshow\s+(me\s+)?(them|it|these|those|all\s*(\s+of\s+them)?)\b", re.IGNORECASE)
_FOLLOW_UP_ORDINAL_RE = re.compile(
    r"\b(the|this|that|show\s+me\s+the|what\s+about\s+the|tell\s+me\s+about\s+the|how\s+much\s+is\s+the)\s+"
    r"(first|second|third|fourth|fifth|last|next|best|cheapest|most\s+expensive)\s+one\b",
    re.IGNORECASE,
)
_FOLLOW_UP_COMPARE_RE = re.compile(r"\bcompare\s+(the\s+first\s+two|them|these|both)\b", re.IGNORECASE)
_FOLLOW_UP_WHICH_RE = re.compile(
    r"\bwhich\s+(one\s+)?is\s+(the\s+)?(cheapest|best|most\s+expensive|better)\b|\b(cheapest|best)\s+one\b",
    re.IGNORECASE,
)
_FOLLOW_UP_DETAILS_RE = re.compile(
    r"\b(give\s+me\s+(more\s+)?details|tell\s+me\s+(more\s+about|about)\s+(it|them)|how\s+much\s+is\s+it)\b",
    re.IGNORECASE,
)


def _product_price_value(price: str | None) -> float | None:
    try:
        value = float(price)
        if value > 0:
            return value
    except (TypeError, ValueError):
        return None
    return None


async def _resolve_follow_up(
    message: str,
    conversation_id: str,
    store_id: str,
    conversation_service: ConversationService,
    stored_context: dict | None = None,
) -> dict | None:
    """Resolve contextual follow-ups against the conversation's last recommendation.

    Returns a widget block (type/products/product) or None when the follow-up
    cannot be resolved from structured context (falls through to the coordinator).
    """
    if stored_context is None:
        stored_context = await conversation_service.get_conversation_context(conversation_id, store_id)
    last_recommendation = (stored_context or {}).get("last_recommendation") or {}
    products = last_recommendation.get("products") or []
    if not products:
        return None

    text = message.strip()
    compare = _FOLLOW_UP_COMPARE_RE.search(text)
    if compare:
        first_two = products[:2]
        if len(first_two) == 2:
            return {
                "type": "products",
                "message": "Here's a side-by-side look at the first two products I recommended.",
                "products": first_two,
            }

    which = _FOLLOW_UP_WHICH_RE.search(text)
    if which:
        selector = (which.group(3) or which.group(2) or "").lower()
        priced = [(p, v) for p in products if (v := _product_price_value(p.get("price"))) is not None]
        selected = None
        if selector == "cheapest":
            selected = min(priced, key=lambda pair: pair[1])[0] if priced else None
        elif selector == "most expensive":
            selected = max(priced, key=lambda pair: pair[1])[0] if priced else None
        elif selector == "best":
            selected = min(priced, key=lambda pair: pair[1])[0] if priced else products[0]
        if selected:
            return {
                "type": "product_detail",
                "message": "Here's the best match from the products I recommended:",
                "product": selected,
            }

    ordinal = _FOLLOW_UP_ORDINAL_RE.search(text)
    if ordinal:
        selector = ordinal.group(2).lower()
        selected = None
        if selector == "last":
            selected = products[-1]
        elif selector == "next":
            selected = products[1] if len(products) > 1 else None
        elif selector == "best":
            priced = [(p, v) for p in products if (v := _product_price_value(p.get("price"))) is not None]
            selected = min(priced, key=lambda pair: pair[1])[0] if priced else products[0]
        elif selector == "cheapest":
            priced = [(p, v) for p in products if (v := _product_price_value(p.get("price"))) is not None]
            selected = min(priced, key=lambda pair: pair[1])[0] if priced else None
        elif selector == "most expensive":
            priced = [(p, v) for p in products if (v := _product_price_value(p.get("price"))) is not None]
            selected = max(priced, key=lambda pair: pair[1])[0] if priced else None
        elif selector in _ORDINAL_INDEX:
            idx = _ORDINAL_INDEX[selector]
            selected = products[idx] if idx < len(products) else None

        if selected:
            return {
                "type": "product_detail",
                "message": f"Here's the {ordinal.group(2)} product I mentioned:",
                "product": selected,
            }

    if _FOLLOW_UP_SHOW_ALL_RE.search(text):
        return {
            "type": "products",
            "message": "Here are the products I recommended earlier:",
            "products": products,
        }

    if _FOLLOW_UP_DETAILS_RE.search(text):
        return {
            "type": "product_detail",
            "message": "Here are the details of the first product I recommended:",
            "product": products[0],
        }

    return None


def _last_recommendation_context(query: str, products: list[dict]) -> dict:
    """Structured context block persisted after a recommendation result."""
    return {
        "query": query,
        "product_ids": [p.get("product_id") for p in products if p.get("product_id")],
        "products": products,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


async def _persist_chat_context(
    conversation_service: ConversationService,
    conversation_id: str,
    store_id: str,
    user_input: str,
    response: ChatResponse,
    previous_routing: dict | None = None,
) -> None:
    """Persist structured conversation context from an orchestrated chat turn."""
    metadata = response.metadata or {}
    structured = metadata.get("result") or {}
    context_update: dict = {}

    if structured.get("products"):
        context_update["last_recommendation"] = _last_recommendation_context(
            user_input,
            structured["products"],
        )
    if structured.get("bundle"):
        context_update["last_bundle"] = {
            "query": user_input,
            "bundle": structured["bundle"],
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    if structured.get("ticket_created"):
        context_update["last_ticket"] = {"created": True}
    if (
        metadata.get("sub_agent") == "escalation"
        or structured.get("escalation_needed")
        or (metadata.get("escalation") or {}).get("should_escalate")
    ):
        context_update["last_escalation"] = {"requested": True}

    active_intent = structured.get("intent") or metadata.get("intent")
    if active_intent:
        context_update["routing"] = {
            "active_intent": active_intent,
            "previous_intent": (previous_routing or {}).get("active_intent"),
            "source": (previous_routing or {}).get("source"),
            "reason": (previous_routing or {}).get("reason"),
        }

    if context_update:
        await conversation_service.update_conversation_context(
            conversation_id,
            context_update,
            store_id,
        )


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
    context_builder: ContextBuilder = Depends(get_context_builder),
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
    await conversation_service.get_or_create_conversation(
        conversation_id,
        provider="orchestration",
        model=policy_result.model,
        metadata={"widget_id": widget_id, "path": "widget.chat"},
        store_id=tenant_context.store_id,
    )

    stored_context: dict[str, Any] = {}
    try:
        stored_context = await conversation_service.get_conversation_context(
            conversation_id,
            tenant_context.store_id,
        )
    except Exception:
        logger.debug("Conversation context unavailable (store=%s)", tenant_context.store_id, exc_info=True)

    message_id = payload.message_id or str(uuid.uuid4())
    widget_session_id = getattr(request.state, "widget_session_id", "")
    log_flow_event(
        "widget.chat.start",
        message_id=message_id,
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        widget_id=widget_id,
        session_id=widget_session_id,
        conversation_id=conversation_id,
        customer_id=payload.customer_id,
        path="widget.chat",
        message_len=len(payload.message),
    )

    gate = classify_widget_message(payload.message)

    if gate.category in (GateCategory.PROMPT_INJECTION, GateCategory.UNSAFE_REQUEST, GateCategory.OUT_OF_SCOPE):
        logger.info(
            "Widget chat gate rejected %s (store=%s widget=%s)",
            gate.category.value,
            tenant_context.store_id,
            widget_id,
        )

        async def rejected_execute():
            reply = gate.reply or "I can help with this store's products, orders, policies, and support."
            await conversation_service.save_interaction(
                conversation_id=conversation_id,
                user_message=MessageDTO(role="user", content=payload.message),
                assistant_message=MessageDTO(role="assistant", content=reply),
                usage=UsageDTO(),
                latency_ms=0.0,
                store_id=tenant_context.store_id,
            )
            response = _canned_chat_response(reply, policy_result.model)
            return response, response.usage

        result, _usage = await enforcer.run(
            store_id=tenant_context.store_id,
            organization_id=tenant_context.organization_id,
            session_id=widget_session_id,
            conversation_id=conversation_id,
            echo_text=payload.message,
            model=policy_result.model,
            request_metadata={"widget_id": widget_id, "path": "widget.chat", "gate": gate.category.value},
            execute=rejected_execute,
        )

        _log_widget_chat_complete(
            message_id,
            store_id=tenant_context.store_id,
            conversation_id=conversation_id,
            response_type="text",
            gate=gate.category.value,
            model=result.model,
            provider=result.provider,
        )

        return WidgetChatResponseSchema(
            response=result.message.content,
            citations=[],
            chunk_references=[],
            confidence_score=1.0,
            latency_ms=0.0,
            model=result.model,
            provider=result.provider,
            usage=result.usage.model_dump() if result.usage else UsageDTO().model_dump(),
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=get_request_id(),
        )

    if gate.category is GateCategory.GENERAL_GREETING:
        logger.info(
            "Widget chat gate short-circuited greeting (store=%s widget=%s)",
            tenant_context.store_id,
            widget_id,
        )

        async def greeting_execute():
            await conversation_service.save_interaction(
                conversation_id=conversation_id,
                user_message=MessageDTO(role="user", content=payload.message),
                assistant_message=MessageDTO(role="assistant", content=GREETING_REPLY),
                usage=UsageDTO(),
                latency_ms=0.0,
                store_id=tenant_context.store_id,
            )
            response = _canned_chat_response(GREETING_REPLY, policy_result.model, "text")
            return response, response.usage

        result, _usage = await enforcer.run(
            store_id=tenant_context.store_id,
            organization_id=tenant_context.organization_id,
            session_id=widget_session_id,
            conversation_id=conversation_id,
            echo_text=payload.message,
            model=policy_result.model,
            request_metadata={"widget_id": widget_id, "path": "widget.chat", "gate": "greeting"},
            execute=greeting_execute,
        )

        _log_widget_chat_complete(
            message_id,
            store_id=tenant_context.store_id,
            conversation_id=conversation_id,
            response_type="text",
            gate="greeting",
            model=result.model,
            provider=result.provider,
        )

        return WidgetChatResponseSchema(
            response=result.message.content,
            citations=[],
            chunk_references=[],
            confidence_score=1.0,
            latency_ms=0.0,
            model=result.model,
            provider=result.provider,
            usage=result.usage.model_dump() if result.usage else UsageDTO().model_dump(),
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=get_request_id(),
        )

    if gate.category is GateCategory.CONTEXTUAL_FOLLOW_UP:
        resolved = await _resolve_follow_up(
            payload.message,
            conversation_id,
            tenant_context.store_id,
            conversation_service,
            stored_context=stored_context,
        )
        if resolved:
            logger.info(
                "Widget chat gate resolved contextual follow-up (store=%s widget=%s)",
                tenant_context.store_id,
                widget_id,
            )

            async def follow_up_execute():
                reply_text = resolved.get("message") or "Here you go:"
                await conversation_service.save_interaction(
                    conversation_id=conversation_id,
                    user_message=MessageDTO(role="user", content=payload.message),
                    assistant_message=MessageDTO(role="assistant", content=reply_text),
                    usage=UsageDTO(),
                    latency_ms=0.0,
                    store_id=tenant_context.store_id,
                )
                response = _canned_chat_response(
                    reply_text,
                    policy_result.model,
                    resolved.get("type", "text"),
                    {
                        "products": resolved.get("products"),
                        "product": resolved.get("product"),
                    },
                )
                return response, response.usage

            result, _usage = await enforcer.run(
                store_id=tenant_context.store_id,
                organization_id=tenant_context.organization_id,
                session_id=widget_session_id,
                conversation_id=conversation_id,
                echo_text=payload.message,
                model=policy_result.model,
                request_metadata={"widget_id": widget_id, "path": "widget.chat", "gate": "contextual_follow_up"},
                execute=follow_up_execute,
            )

            follow_up_type = result.metadata.get("widget", {}).get("type", "text")
            _log_widget_chat_complete(
                message_id,
                store_id=tenant_context.store_id,
                conversation_id=conversation_id,
                response_type=follow_up_type,
                gate="contextual_follow_up",
                model=result.model,
                provider=result.provider,
            )

            return WidgetChatResponseSchema(
                response=result.message.content,
                citations=[],
                chunk_references=[],
                confidence_score=1.0,
                latency_ms=0.0,
                model=result.model,
                provider=result.provider,
                usage=result.usage.model_dump() if result.usage else UsageDTO().model_dump(),
                conversation_id=conversation_id,
                type=follow_up_type,
                products=result.metadata.get("widget", {}).get("products") or [],
                product=result.metadata.get("widget", {}).get("product"),
                message_id=message_id,
                request_id=get_request_id(),
            )

    retrieval_start = time.perf_counter()
    ai_context = await context_builder.build(
        message=payload.message,
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        conversation_id=conversation_id,
        customer_id=payload.customer_id,
        language=payload.language,
        knowledge_scope=policy_result.knowledge_scope,
        policy={
            "top_k": min(policy_result.top_k, MAX_CHUNKS_IN_CONTEXT),
            "score_threshold": policy_result.score_threshold,
            "use_hybrid": policy_result.use_hybrid,
            "use_mmr": policy_result.use_mmr,
            "rerank": policy_result.rerank,
        },
        tenant={
            "organization_id": tenant_context.organization_id,
            "store_id": tenant_context.store_id,
            "widget_id": widget_id,
        },
        conversation_context=stored_context,
    )
    retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000
    chunks = deduplicate_chunks(ai_context.chunks())
    log_flow_event(
        "retrieval.complete",
        message_id=message_id,
        store_id=tenant_context.store_id,
        organization_id=tenant_context.organization_id,
        conversation_id=conversation_id,
        chunk_count=len(chunks),
        intent=ai_context.intent,
        strategy="hybrid" if policy_result.use_hybrid else "vector",
        knowledge_scope=policy_result.knowledge_scope,
        latency_ms=round(retrieval_latency_ms, 3),
    )

    business_rules = ai_context.business_rules or {}
    has_business_summary = bool(business_rules.get("business_summary"))

    history = list(ai_context.history)

    async def execute():
        start_time = time.perf_counter()
        response = await orchestration_service.chat(
            user_input=payload.message,
            store_id=tenant_context.store_id,
            customer_id=payload.customer_id,
            conversation_id=conversation_id,
            history=history,
            context=ai_context.to_dict(),
            metadata={
                "widget_id": widget_id,
                "session_id": widget_session_id,
                "path": "widget.chat",
                "message_id": message_id,
            },
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
        await _persist_chat_context(
            conversation_service,
            conversation_id,
            tenant_context.store_id,
            payload.message,
            response,
            previous_routing=(stored_context or {}).get("routing"),
        )
        log_flow_event(
            "orchestration.complete",
            message_id=message_id,
            store_id=tenant_context.store_id,
            conversation_id=conversation_id,
            intent=(response.metadata or {}).get("intent"),
            sub_agent=(response.metadata or {}).get("sub_agent"),
            latency_ms=round(latency_ms, 3),
            model=response.model,
            provider=response.provider,
            total_tokens=response.usage.total_tokens if response.usage else 0,
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
    sub_agent = (result.metadata or {}).get("sub_agent")
    structured_result = (result.metadata or {}).get("result") or {}
    escalation_decision = (result.metadata or {}).get("escalation") or {}
    answer_text = result.message.content if isinstance(result.message.content, str) else str(result.message.content)

    response_type: str = "text"
    products: list[dict] = []
    product: dict | None = None
    bundle: dict | None = None
    product_payloads: list[ProductPayload] = []
    bundle_payload: BundlePayload | None = None

    if sub_agent == "escalation" or escalation_decision.get("should_escalate") or contains_internal_leak(answer_text):
        answer_text = ESCALATION_REPLY
        response_type = "escalation"
    else:
        answer_text = scrub_internal_labels(answer_text)
        if structured_result.get("products") and sub_agent in ("recommendation", "sales", "product_information"):
            product_payloads = [
                ProductPayload.model_validate(p) for p in structured_result["products"] if isinstance(p, dict)
            ]
            products = [p.model_dump() for p in product_payloads]
            response_type = "products"
        elif structured_result.get("bundle") and sub_agent == "bundle":
            bundle_payload = BundlePayload.model_validate(structured_result["bundle"])
            bundle = bundle_payload.model_dump()
            response_type = "bundle"

    confidence = _widget_confidence_score(intent, chunks, has_business_summary)
    if response_type in ("escalation", "products", "bundle", "product_detail"):
        confidence = 1.0

    _log_widget_chat_complete(
        message_id,
        store_id=tenant_context.store_id,
        conversation_id=conversation_id,
        response_type=response_type,
        product_count=len(products),
        bundle_present=bundle is not None,
        promo_code_present=(bundle or {}).get("promo_code") is not None,
        escalation=response_type == "escalation",
        model=result.model,
        provider=result.provider,
        latency_ms=result.latency_ms,
    )

    if response_type == "bundle":
        await _track_bundle_events(
            store_id=tenant_context.store_id,
            bundle=bundle,
            conversation_id=conversation_id,
            customer_id=payload.customer_id,
        )

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
        confidence_score=confidence,
        latency_ms=result.latency_ms,
        model=result.model,
        provider=result.provider,
        usage=result.usage.model_dump() if result.usage else UsageDTO().model_dump(),
        business_summary_version=business_rules.get("business_summary_version"),
        conversation_id=conversation_id,
        type=response_type,
        products=products,
        product=product,
        bundle=bundle,
        message_id=message_id,
        request_id=get_request_id(),
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
    conversation_service: ConversationService = Depends(get_conversation_service),
    enforcer: QuotaEnforcer = Depends(get_quota_enforcer),
) -> WidgetRecommendationResponseSchema:
    plan = await enforcer.resolve_plan(tenant_context.store_id)

    conversation_id = payload.conversation_id or ""
    if conversation_id:
        owned = await conversation_service.conversation_owned_by_store(
            conversation_id,
            tenant_context.store_id,
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

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
        conversation_id=conversation_id,
        echo_text=payload.message,
        model=plan.fallback_model,
        request_metadata={"widget_id": getattr(request.state, "widget_id", ""), "path": "widget.recommendations"},
        execute=execute,
    )

    products = [
        {
            "product_id": p.product_id,
            "title": p.title,
            "price": str(p.price),
            "currency": p.currency,
            "image_url": p.image_url,
            "product_url": p.product_url,
            "specs": [s.model_dump() for s in p.specs],
            "match_reasons": p.match_reasons,
            "discount_pct": p.discount_pct,
            "discount_available": p.discount_available,
            "final_price": str(p.final_price) if p.final_price is not None else None,
            "in_stock": p.in_stock,
        }
        for p in result.products
    ]

    if conversation_id and products:
        await conversation_service.update_conversation_context(
            conversation_id,
            {"last_recommendation": _last_recommendation_context(payload.message, products)},
            tenant_context.store_id,
        )

    return WidgetRecommendationResponseSchema(
        query=result.query,
        products=products,
        rationale=result.rationale,
        total_count=result.total_count,
        latency_ms=result.latency_ms,
        customer_id=result.customer_id,
        type=result.type,
        budget=result.budget,
        discount_available=result.discount_available,
        discount=result.discount,
        final_price=result.final_price,
    )


@router.post(
    "/bundles/events",
    response_model=WidgetBundleEventResponseSchema,
    summary="Record a widget bundle funnel event (clicked, promo copied/applied)",
    dependencies=[Depends(require_widget_scope("recommendations:read"))],
)
async def widget_bundle_event(
    payload: WidgetBundleEventRequestSchema,
    tenant_context: TenantContext = Depends(get_widget_tenant_context),
) -> WidgetBundleEventResponseSchema:
    """Frontend -> analytics hook for bundle_clicked / promo_copied / promo_applied (Fix 5.6)."""
    try:
        result = await BundleTrackingService().track_event(
            store_id=tenant_context.store_id,
            event=payload.event,
            conversation_id=payload.conversation_id,
            customer_id=payload.customer_id,
            product_ids=payload.product_ids,
            discount_pct=payload.discount_pct,
            promo_code=payload.promo_code,
            bundle_key=payload.bundle_key,
        )
    except Exception as exc:
        logger.warning("Failed to record widget bundle event '%s': %s", payload.event, exc)
        return WidgetBundleEventResponseSchema(event=payload.event, recorded=False)
    return WidgetBundleEventResponseSchema(event=payload.event, recorded=result.get("recorded", False))
