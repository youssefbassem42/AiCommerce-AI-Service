"""Conversation-aware intent resolution for the widget chat path.

Resolves the intent for a single user message with deterministic signals
first — explicit human requests, support/policy keywords, product-information
phrasing, bundle lists, and short follow-up continuation of the active flow —
and an LLM classification as the backstop.

The resolver NEVER returns ``escalation``: frustrated or human-seeking
messages route to ``support`` and only the escalation decision engine may
raise a ticket (the decision engine owns escalation).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.agents.coordinator.tools import classify_intent
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Intents a short follow-up ("$50", "black", "yes") may continue.
CONTINUABLE_INTENTS = {"recommendation", "sales", "bundle", "product_information", "support"}

HUMAN_REQUEST_PATTERNS = (
    re.compile(r"\btalk\s+to\s+(?:a|the|someone|a\s+real)\s+(?:human|person|agent|representative)\b", re.IGNORECASE),
    re.compile(r"\bspeak\s+to\s+(?:a|the|someone|a\s+real)\s+(?:human|person|agent|representative)\b", re.IGNORECASE),
    re.compile(r"\breal\s+(?:human|person|agent)\b", re.IGNORECASE),
    re.compile(r"\bhuman\s+agent\b", re.IGNORECASE),
    re.compile(r"\bescalate\b", re.IGNORECASE),
    re.compile(r"\bopen\s+a\s+ticket\b", re.IGNORECASE),
    re.compile(r"\bconnect\s+me\s+to\b", re.IGNORECASE),
    re.compile(r"\btransfer\s+me\b", re.IGNORECASE),
    re.compile(r"\bi\s+want\s+a\s+human\b", re.IGNORECASE),
)

# Support/policy keywords take precedence over shopping continuation.
SUPPORT_KEYWORDS = (
    "return policy",
    "refund",
    "shipping",
    "delivery",
    "tracking",
    "track my order",
    "order status",
    "my order",
    "cancel",
    "charge",
    "charged",
    "payment",
    "account",
    "password",
    "login",
    "sign in",
    "warranty claim",
    "billing",
    "help me",
    "support",
)

PRODUCT_INFO_PATTERNS = (
    re.compile(r"^(?:tell|talk|speak)\s+(?:me\s+)?about\b", re.IGNORECASE),
    re.compile(
        r"\bwhat(?:\'s| is| are)\s+(?:the\s+)?"
        r"(?:dimensions|specifications|specs|features|material|weight|size|colors|colours|difference)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwhat\s+(?:specs|specifications|features|dimensions|colors|colours|material|weight|size|included)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bhow\s+(?:big|large|heavy|wide|tall|long)\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+(?:it|this|the)\s+(?:have|come|support|work)\b", re.IGNORECASE),
    re.compile(r"\bis\s+it\s+available\s+in\b", re.IGNORECASE),
    re.compile(r"\bdoes\s+it\s+come\s+in\b", re.IGNORECASE),
    re.compile(r"\bwhat\b[^.]{0,60}\b(?:included|in the box|comes with)\b", re.IGNORECASE),
)

BUNDLE_WORDS = (
    "bundle",
    "bundles",
    "combo",
    "kit",
    "package",
    "promo code",
    "promo codes",
    "coupon",
    "coupons",
    "discount code",
    "discount codes",
)

PURCHASE_VERBS = (
    "want",
    "need",
    "buy",
    "get",
    "looking for",
    "would like",
    "recommend",
    "recommendation",
    "order",
)

SPEC_DETAIL = re.compile(r"\b\d+\s*(?:gb|tb|inch|inches|mp|hz|w)\b", re.IGNORECASE)

USE_CASE_PHRASES = (
    "for gaming",
    "for work",
    "for school",
    "for cooking",
    "for home office",
    "for weddings",
    "for daily use",
    "for travel",
    "for streaming",
    "for content creation",
    "for photography",
    "for fitness",
    "for running",
    "for kids",
    "for students",
    "for office",
    "for college",
)

COLORS = {
    "black",
    "white",
    "blue",
    "red",
    "green",
    "yellow",
    "pink",
    "purple",
    "orange",
    "brown",
    "grey",
    "gray",
    "gold",
    "silver",
    "beige",
    "navy",
    "teal",
    "cream",
    "tan",
}

SIZES = {"small", "medium", "large", "xl", "xxl", "xs", "big", "compact", "mini"}

AFFIRMATIONS = {
    "yes",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "sounds good",
    "perfect",
    "great",
    "no",
    "nope",
    "not really",
    "not sure",
}

DEICTIC_PATTERN = re.compile(r"^(?:the\s+)?(?:first|second|third|last|other|one|this|that)\s+one$", re.IGNORECASE)

BUDGET_PATTERN = re.compile(
    r"^\s*(?:under|less\s+than|below|around|about|at\s+most|max(?:imum)?|no\s+more\s+than)?\s*"
    r"\$?\s*\d{1,7}(?:[.,]\d{1,2})?\s*(?:usd|dollars?|\$)?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IntentResolution:
    """Result of intent resolution with provenance for observability."""

    intent: str
    confidence: float
    source: str
    reason: str


def _matches_support_keywords(message: str) -> bool:
    return any(re.search(rf"\b{re.escape(keyword)}\b", message) for keyword in SUPPORT_KEYWORDS)


def _matches_product_info(message: str) -> bool:
    return any(pattern.search(message) for pattern in PRODUCT_INFO_PATTERNS)


def detect_bundle_request(message: str) -> bool:
    """Deterministic bundle signals: bundle words or a multi-item list.

    Guarded so spec-laden ("16gb ram and 1tb ssd"), use-case framed
    ("for gaming"), color-only ("black and white") and support/policy
    ("returns and shipping") messages are never misrouted to the bundle agent.
    """
    msg = message.strip().lower()
    if not msg:
        return False
    if _matches_support_keywords(msg):
        return False
    if SPEC_DETAIL.search(msg):
        return False
    if any(phrase in msg for phrase in USE_CASE_PHRASES):
        return False
    if any(word in msg for word in BUNDLE_WORDS):
        return True
    if re.search(r"(?:complete|full)\s+(?:gaming\s+|pc\s+|setup\s+)?(?:setup|build|rig)", msg):
        return True
    if "everything" in msg:
        return True
    if re.search(r"\band\b|\s\+", msg):
        color_tokens = [w.strip() for w in re.split(r"\band\b|\s\+", msg) if w.strip()]
        if color_tokens and all(w in COLORS or w in SIZES for w in color_tokens):
            return False
        if any(verb in msg for verb in PURCHASE_VERBS):
            return True
        if len(msg.split()) <= 5 and not re.match(
            r"^(?:i'm|i am|im|why|how|does|do|can|what|who|is|are|it|this|that|my|the|a)\b",
            msg,
        ):
            return True
    return False


def detect_continuation(message: str, previous_intent: str | None) -> bool:
    """Short follow-up signals that continue the active intent."""
    if previous_intent not in CONTINUABLE_INTENTS:
        return False
    msg = message.strip().lower()
    if not msg:
        return False
    if BUDGET_PATTERN.fullmatch(msg):
        return True
    if msg in COLORS or msg in SIZES:
        return True
    if msg in AFFIRMATIONS:
        return True
    if DEICTIC_PATTERN.fullmatch(msg):
        return True
    if any(phrase in msg for phrase in USE_CASE_PHRASES):
        return True
    return bool(SPEC_DETAIL.search(msg))


async def resolve_intent(
    message: str,
    *,
    llm: BaseLLMProvider | None = None,
    history: str = "",
    previous_intent: str | None = None,
    shopping_state: Any = None,
) -> IntentResolution:
    """Resolve the intent for one message with deterministic signals first."""
    msg = message.strip().lower()

    if any(pattern.search(msg) for pattern in HUMAN_REQUEST_PATTERNS):
        return IntentResolution("support", 0.95, "deterministic", "explicit human request")
    if _matches_support_keywords(msg):
        return IntentResolution("support", 0.9, "deterministic", "support/policy keyword")
    if _matches_product_info(msg):
        return IntentResolution("product_information", 0.9, "deterministic", "product information phrasing")
    if detect_bundle_request(msg):
        return IntentResolution("bundle", 0.85, "deterministic", "multi-item bundle request")
    if previous_intent in CONTINUABLE_INTENTS and detect_continuation(message, previous_intent):
        return IntentResolution(previous_intent, 0.9, "continuation", "short follow-up continuing active flow")

    hint = f"Previous intent: {previous_intent}\n" if previous_intent else ""
    if shopping_state is not None:
        try:
            prompt_text = shopping_state.to_prompt_text()
            if prompt_text:
                hint += f"Known shopping state: {prompt_text}\n"
        except Exception:
            logger.debug("Shopping state prompt text unavailable", exc_info=True)

    try:
        intent, confidence = await classify_intent(
            user_input=message,
            history=hint + history,
            llm=llm,
        )
    except Exception as exc:
        logger.warning("Intent classification failed in resolver: %s", exc, exc_info=True)
        if previous_intent in CONTINUABLE_INTENTS:
            return IntentResolution(previous_intent, 0.4, "fallback", "classifier failure kept active flow")
        return IntentResolution("general", 0.2, "fallback", "classifier failure")

    if intent == "escalation":
        return IntentResolution("support", confidence, "llm-normalized", "escalation label normalized to support")
    return IntentResolution(intent, confidence, "llm", "LLM classification")
