"""Context Builder: assembles the canonical AIContext for one chat message.

Order of assembly (per Phase 2 design):

    Message
     ↓
    Context Builder
     ├── conversation  (history)
     ├── memory        (recalled session/user memory)
     ├── RAG           (intent-specific retrieval)
     ├── store context (business summary / capabilities)
     └── user context  (customer profile, intent, entities)
     ↓
    Coordinator
     ↓
    Agent

The coordinator MERGES this context (Fix 2.2) instead of reloading and
overwriting it, so the RAG context built here always reaches the sub-agents.
"""

from __future__ import annotations

import logging
from typing import Any

from app.application.context.ai_context import AIContext
from app.application.context.intent_resolver import resolve_intent
from app.application.context.retrieval_planner import PRODUCT_ENTITY_TYPES, RetrievalPlan, plan_for_intent
from app.application.context.shopping_state import SESSION_STATE_KEY, shopping_state_from_context
from app.application.knowledge.retrieval.config import RetrievalConfig, RetrievalFilters
from app.application.knowledge.retrieval.dto import RetrievedChunkDTO
from app.application.knowledge.retrieval.service import RetrieverService
from app.application.services.conversation_service import ConversationService
from app.domain.customer.repositories.customer_repository import ICustomerRepository
from app.domain.knowledge.repositories.business_summary_repository import BusinessSummaryRepository
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

MAX_KNOWLEDGE_CHUNKS = 6
MAX_PRODUCT_CARDS = 10


def _chunk_to_dict(chunk: RetrievedChunkDTO) -> dict[str, Any]:
    return chunk.model_dump()


def _chunk_to_product_card(chunk: RetrievedChunkDTO) -> dict[str, Any] | None:
    """Consumer-safe product card from a product-typed chunk (canonical payload)."""
    payload = chunk.metadata or {}
    if payload.get("entity_type") != "product":
        return None
    product_id = payload.get("product_id") or chunk.chunk_id
    if not product_id:
        return None
    return {
        "product_id": product_id,
        "title": payload.get("product_title") or chunk.document_title or "Unknown Product",
        "price": payload.get("price"),
        "currency": payload.get("currency", "USD"),
        "image_url": payload.get("image_url"),
        "product_url": payload.get("product_url"),
        "specs": payload.get("specs") or [],
        "match_score": chunk.score,
    }


def _filters_for_plan(
    plan: RetrievalPlan,
    *,
    organization_id: str | None,
    store_id: str,
    language: str | None,
    knowledge_scope: str | None,
) -> RetrievalFilters:
    """Build tenant-scoped retrieval filters from an intent plan (metadata filtering)."""
    return RetrievalFilters(
        organization_id=organization_id,
        store_id=store_id,
        language=language,
        knowledge_scope=knowledge_scope or (plan.knowledge_scopes[0] if plan.knowledge_scopes else None),
        entity_type=None,
        entity_types=list(plan.entity_types) if plan.entity_types else None,
    )


def _config_for_plan(
    plan: RetrievalPlan,
    *,
    policy_top_k: int | None,
    policy_score_threshold: float | None,
    policy_use_hybrid: bool | None,
    policy_use_mmr: bool | None,
    policy_rerank: bool | None,
) -> RetrievalConfig:
    """Build the retrieval config for a plan, honoring server policy bounds."""
    top_k = min(plan.top_k, policy_top_k or plan.top_k)
    use_mmr = policy_use_mmr if policy_use_mmr is not None else plan.use_mmr
    if plan.entity_types == PRODUCT_ENTITY_TYPES:
        use_mmr = False
    return RetrievalConfig(
        top_k=top_k,
        score_threshold=policy_score_threshold if policy_score_threshold is not None else plan.score_threshold or 0.25,
        use_hybrid=policy_use_hybrid if policy_use_hybrid is not None else plan.use_hybrid,
        use_mmr=use_mmr,
        rerank=policy_rerank if policy_rerank is not None else plan.rerank,
        rerank_top_k=min(plan.top_k, 10),
    )


async def _load_business_rules(
    summary_repository: BusinessSummaryRepository | None,
    store_id: str,
) -> dict[str, Any]:
    if not summary_repository:
        return {}
    try:
        summaries = await summary_repository.find_by_document_id(store_id)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load business summary for store '%s': %s", store_id, exc)
        return {}
    if not summaries:
        return {}
    latest = max(summaries, key=lambda s: (s.version_number, s.created_at))
    return {
        "business_summary": latest.summary,
        "business_summary_version": latest.version_number,
    }


class ContextBuilder:
    """Assembles the canonical AIContext for a chat message."""

    def __init__(
        self,
        retriever_service: RetrieverService,
        llm: BaseLLMProvider,
        conversation_service: ConversationService | None = None,
        summary_repository: BusinessSummaryRepository | None = None,
        memory_agent: Any | None = None,
        customer_repo: ICustomerRepository | None = None,
    ):
        self._retriever = retriever_service
        self._llm = llm
        self._conversation_service = conversation_service
        self._summary_repo = summary_repository
        self._memory_agent = memory_agent
        self._customer_repo = customer_repo

    async def _load_history(
        self,
        conversation_id: str | None,
        store_id: str,
        provided: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if provided:
            return provided
        if not conversation_id or not self._conversation_service:
            return []
        try:
            messages = await self._conversation_service.get_conversation_history(conversation_id, store_id=store_id)
            return [
                {"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}
                for m in messages
            ]
        except Exception as exc:
            logger.warning("Failed to load conversation history: %s", exc)
            return []

    async def _load_memory(self, conversation_id: str | None, customer_id: str | None, store_id: str) -> dict[str, Any]:
        if not self._memory_agent or not conversation_id:
            return {}
        try:
            result = await self._memory_agent.recall(
                session_id=conversation_id,
                user_id=customer_id,
                store_id=store_id,
            )
            retrieved = result.get("retrieved") or {}
            return {
                "recall_source": retrieved.get("source"),
                "entries": retrieved.get("all") or (retrieved if "all" not in retrieved else {}),
            }
        except Exception as exc:
            logger.warning("Memory recall failed: %s", exc)
            return {}

    async def _load_customer(self, customer_id: str | None) -> dict[str, Any] | None:
        if not customer_id or not self._customer_repo:
            return None
        try:
            customer = await self._customer_repo.find_by_id(customer_id)
            if customer is None:
                return None
            data = {}
            for attr in ("id", "email", "first_name", "last_name", "phone", "city", "country"):
                value = getattr(customer, attr, None)
                if value is not None:
                    data[attr] = str(value)
            return data or {"customer_id": customer_id}
        except Exception as exc:
            logger.warning("Customer lookup failed for '%s': %s", customer_id, exc)
            return None

    async def _retrieve(
        self,
        query: str,
        plan: RetrievalPlan,
        *,
        organization_id: str | None,
        store_id: str,
        language: str | None,
        knowledge_scope: str | None,
        policy: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Run intent-specific retrieval; returns (knowledge chunks, product cards)."""
        policy = policy or {}
        filters = _filters_for_plan(
            plan,
            organization_id=organization_id,
            store_id=store_id,
            language=language,
            knowledge_scope=knowledge_scope,
        )
        config = _config_for_plan(
            plan,
            policy_top_k=policy.get("top_k"),
            policy_score_threshold=policy.get("score_threshold"),
            policy_use_hybrid=policy.get("use_hybrid"),
            policy_use_mmr=policy.get("use_mmr"),
            policy_rerank=policy.get("rerank"),
        )
        try:
            result = await self._retriever.search(query=query, filters=filters, config=config)
        except Exception as exc:
            logger.warning("Retrieval failed for intent plan: %s", exc, exc_info=True)
            return [], []

        chunks = [_chunk_to_dict(c) for c in result.results[:MAX_KNOWLEDGE_CHUNKS]]
        products: list[dict[str, Any]] = []
        if plan.include_products:
            for chunk in result.results:
                card = _chunk_to_product_card(chunk)
                if card and card.get("product_id") and len(products) < MAX_PRODUCT_CARDS:
                    products.append(card)
        return chunks, products

    async def build(
        self,
        message: str,
        *,
        store_id: str,
        organization_id: str | None = None,
        conversation_id: str | None = None,
        customer_id: str | None = None,
        language: str | None = None,
        knowledge_scope: str | None = None,
        history: list[dict[str, Any]] | None = None,
        intent: str | None = None,
        policy: dict[str, Any] | None = None,
        tenant: dict[str, Any] | None = None,
        conversation_context: dict[str, Any] | None = None,
    ) -> AIContext:
        """Assemble the full canonical context for one message."""
        context = AIContext(
            tenant=tenant or {"organization_id": organization_id, "store_id": store_id},
            conversation={"conversation_id": conversation_id, "customer_id": customer_id},
            history=[],
        )

        context.history = await self._load_history(conversation_id, store_id, provided=history)
        context.memory = await self._load_memory(conversation_id, customer_id, store_id)
        context.customer = await self._load_customer(customer_id)
        context.business_rules = await _load_business_rules(self._summary_repo, store_id)

        # Seed the durable shopping state from the conversation record when
        # session memory (Redis) does not already carry it, so the shopping
        # goal survives memory loss/expiry (Phase 4). Recalled memory wins.
        stored_shopping_state = (conversation_context or {}).get(SESSION_STATE_KEY) or {}
        memory_entries = context.memory.get("entries") if isinstance(context.memory, dict) else None
        if stored_shopping_state and not (isinstance(memory_entries, dict) and memory_entries.get(SESSION_STATE_KEY)):
            context.conversation[SESSION_STATE_KEY] = stored_shopping_state

        routing = (conversation_context or {}).get("routing") or {}
        previous_intent = routing.get("active_intent") or routing.get("previous_intent")
        shopping_state = shopping_state_from_context(conversation_context)

        if not intent:
            resolution = await resolve_intent(
                message,
                llm=self._llm,
                history="\n".join(f"{m.get('role')}: {m.get('content', '')}" for m in context.history[-8:]),
                previous_intent=previous_intent,
                shopping_state=shopping_state,
            )
            context.intent = resolution.intent
            context.confidence = resolution.confidence
            context.conversation["routing"] = {
                "active_intent": resolution.intent,
                "previous_intent": previous_intent,
                "source": resolution.source,
                "reason": resolution.reason,
            }
        else:
            context.intent = intent
            context.conversation["routing"] = {
                "active_intent": intent,
                "previous_intent": previous_intent,
                "source": "provided",
                "reason": "intent supplied by caller",
            }

        plan = plan_for_intent(context.intent)
        context.knowledge_context, context.products = await self._retrieve(
            message,
            plan,
            organization_id=organization_id,
            store_id=store_id,
            language=language,
            knowledge_scope=knowledge_scope,
            policy=policy,
        )
        return context
