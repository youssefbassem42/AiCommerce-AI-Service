"""Intent-specific retrieval plans for the Context Builder.

Each intent retrieves only the knowledge it needs:

    support / escalation      — FAQ, policies, knowledge
    product_information       — products
    recommendation / sales    — products
    bundle                    — products (plus business rules/promotions)
    general / unknown         — support knowledge (safe fallback, never unfiltered)

The plan drives the retrieval filters (entity_type, knowledge_scope) and the
quality knobs (top_k, score_threshold, hybrid, MMR, rerank) so the router
never retrieves everything for every request.

MMR is disabled for catalog (product) plans: MMR maximizes document diversity,
which promotes irrelevant products for exact product queries. It stays enabled
for support knowledge plans where diversity across FAQ/policy topics helps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.shared.vector_payloads import EntityType

SUPPORT_ENTITY_TYPES: tuple[str, ...] = (EntityType.KNOWLEDGE.value, EntityType.POLICY.value, EntityType.FAQ.value)
PRODUCT_ENTITY_TYPES: tuple[str, ...] = (EntityType.PRODUCT.value,)


@dataclass(frozen=True)
class RetrievalPlan:
    """How to retrieve context for one intent."""

    entity_types: tuple[str, ...] | None = None
    knowledge_scopes: tuple[str, ...] | None = None
    top_k: int = 6
    score_threshold: float | None = None
    use_hybrid: bool = True
    use_mmr: bool = True
    rerank: bool = False
    include_business_summary: bool = True
    include_products: bool = False


def plan_for_intent(intent: str | None) -> RetrievalPlan:
    """Return the retrieval plan for a classified intent.

    Unknown/None intents get the support-knowledge plan (general answering) —
    never an unfiltered retrieval that can leak FAQ or product text into
    general answers (Fix: entity-type isolation).
    """
    if intent in ("support", "escalation"):
        return RetrievalPlan(
            entity_types=SUPPORT_ENTITY_TYPES,
            top_k=6,
            use_hybrid=True,
            use_mmr=True,
            rerank=True,
            include_business_summary=True,
            include_products=False,
        )
    if intent in ("recommendation", "sales", "product_information"):
        return RetrievalPlan(
            entity_types=PRODUCT_ENTITY_TYPES,
            top_k=10,
            use_hybrid=True,
            use_mmr=False,
            rerank=False,
            include_business_summary=False,
            include_products=True,
        )
    if intent == "bundle":
        return RetrievalPlan(
            entity_types=PRODUCT_ENTITY_TYPES,
            top_k=10,
            use_hybrid=True,
            use_mmr=False,
            rerank=False,
            include_business_summary=True,
            include_products=True,
        )
    return RetrievalPlan(
        entity_types=SUPPORT_ENTITY_TYPES,
        top_k=6,
        use_hybrid=True,
        use_mmr=True,
        rerank=True,
        include_business_summary=True,
        include_products=False,
    )


def plan_summary(plan: RetrievalPlan) -> dict[str, Any]:
    """Structured loggable summary of a plan (no internal objects)."""
    return {
        "entity_types": list(plan.entity_types) if plan.entity_types else None,
        "knowledge_scopes": list(plan.knowledge_scopes) if plan.knowledge_scopes else None,
        "top_k": plan.top_k,
        "score_threshold": plan.score_threshold,
        "use_hybrid": plan.use_hybrid,
        "use_mmr": plan.use_mmr,
        "rerank": plan.rerank,
        "include_business_summary": plan.include_business_summary,
        "include_products": plan.include_products,
    }
