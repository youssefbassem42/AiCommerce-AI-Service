"""Canonical contracts for AI flows (Phase 0).

Single import point for intent vocabulary, product/bundle payloads, escalation
decisions, the per-turn conversation trace, and the canonical AI response
schema. All entries are additive; nothing here changes algorithm behavior.
"""

from app.application.contracts.ai_response import AITurnContract
from app.application.contracts.bundle import (
    BundleItemPayload,
    BundlePayload,
    bundle_payload_from_candidates,
)
from app.application.contracts.conversation import ConversationTurnTrace
from app.application.contracts.escalation import EscalationDecision, build_escalation_decision
from app.application.contracts.intent import (
    COMING_SOON_INTENTS,
    EXECUTABLE_INTENTS,
    FALLBACK_INTENTS,
    Intent,
    coerce_intent,
)
from app.application.contracts.product import (
    ProductPayload,
    ProductSpecPayload,
    product_card_to_payload,
)

__all__ = [
    "AITurnContract",
    "BundleItemPayload",
    "BundlePayload",
    "COMING_SOON_INTENTS",
    "ConversationTurnTrace",
    "EscalationDecision",
    "EXECUTABLE_INTENTS",
    "FALLBACK_INTENTS",
    "Intent",
    "ProductPayload",
    "ProductSpecPayload",
    "build_escalation_decision",
    "bundle_payload_from_candidates",
    "coerce_intent",
    "product_card_to_payload",
]
