"""Escalation decision engine.

Deterministic, single source of truth for *when* a turn should hand off to a
human agent. Escalation is the last resort: the AI attempts resolution first
and only escalates when one or more explicit signals fire.

Signals:
- explicit_human_request : the customer explicitly asked for a human
- knowledge_unavailable  : the AI has no grounded knowledge and cannot safely answer
- repeated_failure       : the AI already attempted resolution and the customer is still unresolved
- strong_frustration     : anger/frustration combined with a concrete unresolved problem
- business_rule          : certain issue categories always escalate

Escalation is never triggered by identity (customer_id == null) or by the
mere fact that the customer asked a support question.
"""

from __future__ import annotations

import re
from typing import Any

from app.application.contracts.escalation import EscalationDecision, build_escalation_decision

EXPLICIT_HUMAN_REQUEST = "explicit_human_request"
KNOWLEDGE_UNAVAILABLE = "knowledge_unavailable"
REPEATED_FAILURE = "repeated_failure"
STRONG_FRUSTRATION = "strong_frustration"
BUSINESS_RULE = "business_rule"

HUMAN_REQUEST_PATTERNS: tuple[str, ...] = (
    "talk to a human",
    "talk to human",
    "speak to a human",
    "speak to human",
    "talk to a person",
    "speak to a person",
    "talk to someone",
    "speak to someone",
    "talk to support",
    "speak to support",
    "human support",
    "human agent",
    "real person",
    "real agent",
    "customer service representative",
    "contact support",
    "contact customer service",
    "contact a human",
    "create a ticket",
    "create ticket",
    "open a ticket",
    "open ticket",
    "raise a ticket",
    "raise ticket",
    "file a ticket",
    "file a complaint",
    "i want to speak",
    "i want to talk",
    "connect me to",
    "transfer me",
    "escalate",
    "get me a human",
    "need a human",
    "want a human",
)

FRUSTRATION_TERMS: dict[str, float] = {
    "furious": 1.0,
    "livid": 1.0,
    "enraged": 1.0,
    "infuriated": 1.0,
    "outraged": 1.0,
    "appalled": 0.9,
    "frustrated": 0.8,
    "frustrating": 0.8,
    "useless": 0.9,
    "worthless": 0.9,
    "terrible": 0.8,
    "horrible": 0.9,
    "awful": 0.8,
    "ridiculous": 0.9,
    "absurd": 0.8,
    "unacceptable": 0.9,
    "outrageous": 0.9,
    "disgusting": 0.9,
    "pathetic": 0.9,
    "nightmare": 0.8,
    "mad": 0.7,
    "angry": 0.7,
    "anger": 0.7,
    "fed up": 0.8,
    "sick of": 0.8,
    "tired of": 0.6,
    "hate": 0.6,
    "hated": 0.7,
    "annoying": 0.6,
    "annoyed": 0.6,
    "disappointed": 0.6,
    "disappointing": 0.6,
    "waste": 0.7,
    "wasted": 0.7,
    "worst": 0.8,
    "never": 0.4,
    "stupid": 0.7,
    "dumb": 0.6,
    "embarrassing": 0.7,
    "scam": 0.9,
    "ripped off": 0.9,
    "refund now": 0.9,
}

PROBLEM_INDICATORS: tuple[str, ...] = (
    "order",
    "orders",
    "refund",
    "return",
    "returns",
    "broken",
    "damaged",
    "defective",
    "faulty",
    "wrong item",
    "wrong product",
    "missing",
    "never arrived",
    "not delivered",
    "delivery",
    "shipment",
    "shipping",
    "tracking",
    "charged",
    "charge",
    "charged twice",
    "double charged",
    "payment",
    "account",
    "login",
    "password",
    "can't log in",
    "cannot log in",
    "locked out",
    "cancelled",
    "canceled",
    "not working",
    "doesn't work",
    "does not work",
    "stopped working",
    "won't turn on",
    "not charging",
    "leak",
    "cracked",
    "torn",
    "stained",
    "expired",
    "out of stock",
    "not in stock",
    "never got",
    "never received",
    "didn't receive",
    "did not receive",
    "not received",
    "no confirmation",
    "no tracking",
    "lost",
    "stolen",
)

POLICY_QUESTION_PATTERNS: tuple[str, ...] = (
    "policy",
    "policies",
    "what's your",
    "what is your",
    "what's the",
    "what is the",
    "what are your",
    "how do i",
    "how do you",
    "how can i",
    "can i",
    "could i",
    "do you offer",
    "do you have",
    "is there a",
    "are there any",
    "terms",
    "guidelines",
    "rules",
    "window",
    "how long",
    "opening hours",
    "business hours",
)

# Only account security and payment failures are always escalated. Technical
# and account questions are ordinary support inquiries: the support agent
# tries to resolve them first and the decision engine escalates only when
# resolution fails or a hard signal fires (Fix: no auto-tickets for support
# category questions).
ALWAYS_ESCALATE_CATEGORIES: frozenset[str] = frozenset({"account_security", "payment_failure"})

REPEAT_PATTERNS: tuple[str, ...] = (
    "asked before",
    "asked again",
    "asked twice",
    "asked three times",
    "asked multiple times",
    "already asked",
    "i've asked",
    "i have asked",
    "nobody helps",
    "no one is helping",
    "no one helps",
    "nobody is helping",
    "nobody answered",
    "no one answered",
    "no one responded",
    "nobody responded",
    "still not resolved",
    "still unresolved",
    "still waiting",
    "still haven't",
    "still havent",
    "still nothing",
    "keep asking",
    "kept asking",
    "every time i ask",
    "every time",
    "again and again",
    "third time",
    "3rd time",
    "second time",
    "2nd time",
    "fourth time",
    "multiple times",
    "three times",
    "four times",
    "five times",
    "several times",
    "i've tried",
    "i have tried",
    "already tried",
    "already complained",
    "still not working",
    "still doesn't work",
    "still broken",
    "never get a straight answer",
    "run around",
    "getting nowhere",
)

REPEAT_TIMES_PATTERN = re.compile(
    r"\b(?:three|two|four|five|several|multiple|3|2|4|5|6)\s*(?:times|time)\b",
    re.IGNORECASE,
)

CATEGORY_PRIORITY: dict[str, str] = {
    "account_security": "p1",
    "payment_failure": "p1",
    "refund": "p2",
    "order_status": "p2",
    "returns": "p3",
    "technical": "p3",
    "account": "p3",
    "product_quality": "p4",
    "general": "p4",
    "support": "p3",
}

FRUSTRATION_THRESHOLD = 0.6
SIGNAL_CONFIDENCE: dict[str, float] = {
    EXPLICIT_HUMAN_REQUEST: 0.95,
    BUSINESS_RULE: 0.9,
    REPEATED_FAILURE: 0.85,
    STRONG_FRUSTRATION: 0.8,
    KNOWLEDGE_UNAVAILABLE: 0.7,
}

QUESTION_PATTERN = re.compile(
    r"\?|^(what|where|when|who|why|how|which|can|could|is|are|do|does|did|will|would)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def detect_human_request(text: str) -> bool:
    """True when the customer explicitly asks to speak to a human."""
    normalized = _normalize(text)
    return any(pattern in normalized for pattern in HUMAN_REQUEST_PATTERNS)


def detect_frustration(text: str) -> float:
    """Return a 0..1 frustration score based on lexicon term weights."""
    normalized = _normalize(text)
    score = 0.0
    for term, weight in FRUSTRATION_TERMS.items():
        if term in normalized:
            score = max(score, weight)
    return score


def detect_problem(text: str) -> bool:
    """True when the message states a concrete unresolved problem.

    Vague venting ("your product is terrible") and policy/process questions
    ("what's your return policy?", "how do I return an item?") do not count;
    the customer must describe a specific issue (missing order, broken item,
    double charge, ...).
    """
    normalized = _normalize(text)
    if any(pattern in normalized for pattern in POLICY_QUESTION_PATTERNS):
        return False
    return any(indicator in normalized for indicator in PROBLEM_INDICATORS)


def detect_repeated_failure(user_input: str, history: list[dict[str, Any]] | None = None) -> bool:
    """True when the customer signals prior attempts went unresolved.

    Either the message itself repeats a complaint ("I've asked three times",
    "still not resolved") or the history contains the same question again.
    """
    normalized = _normalize(user_input)
    if REPEAT_TIMES_PATTERN.search(normalized) or any(pattern in normalized for pattern in REPEAT_PATTERNS):
        return True

    if not history:
        return False

    current_words = set(normalized.split())
    similar = 0
    for msg in history[-8:]:
        content = _normalize(msg.get("content", "") if isinstance(msg, dict) else str(msg))
        if not content:
            continue
        words = set(content.split())
        if not words:
            continue
        overlap = len(current_words & words) / len(current_words)
        if overlap >= 0.5:
            similar += 1
    return similar >= 2


def detect_business_rule(category: str | None) -> bool:
    return (category or "").lower() in ALWAYS_ESCALATE_CATEGORIES


def is_inquiry(text: str) -> bool:
    """True when the message reads like a question or a request for help."""
    normalized = _normalize(text)
    if QUESTION_PATTERN.search(normalized):
        return True
    return detect_problem(text)


def priority_for(category: str | None) -> str:
    return CATEGORY_PRIORITY.get((category or "general").lower(), "p4")


def _build_summary(signals: list[str], user_input: str) -> str:
    if EXPLICIT_HUMAN_REQUEST in signals:
        return "Customer explicitly requested to speak to a human agent."
    if BUSINESS_RULE in signals:
        return "Issue category requires human assistance by business rule."
    if REPEATED_FAILURE in signals:
        return "Customer repeated their request and remains unresolved after AI attempts."
    if STRONG_FRUSTRATION in signals:
        return "Customer shows strong frustration with a concrete unresolved problem."
    if KNOWLEDGE_UNAVAILABLE in signals:
        return "AI cannot safely answer: no grounded knowledge is available."
    return f"Escalation requested for: {user_input[:200]}"


def evaluate_escalation(
    *,
    user_input: str,
    history: list[dict[str, Any]] | None = None,
    category: str | None = None,
    knowledge_available: bool = True,
    answered: bool = True,
    customer_id: str | None = None,  # noqa: ARG001 - identity must never trigger escalation
) -> EscalationDecision:
    """Evaluate whether a turn should escalate to a human agent.

    Args:
        user_input: the customer's latest message.
        history: prior conversation messages (user turns).
        category: the classified issue category / intent (e.g. 'support').
        knowledge_available: whether grounded store knowledge was retrieved.
        answered: whether the AI produced a response this turn.
        customer_id: intentionally unused - identity must not trigger escalation.
    """
    signals: list[str] = []
    reasons: list[str] = []

    if detect_human_request(user_input):
        signals.append(EXPLICIT_HUMAN_REQUEST)
        reasons.append("Customer explicitly requested a human agent.")

    if detect_business_rule(category):
        signals.append(BUSINESS_RULE)
        reasons.append(f"Issue category '{category}' always requires human assistance.")

    if detect_repeated_failure(user_input, history):
        signals.append(REPEATED_FAILURE)
        reasons.append("Customer remains unresolved after prior AI attempts.")

    frustration = detect_frustration(user_input)
    if frustration >= FRUSTRATION_THRESHOLD and detect_problem(user_input):
        signals.append(STRONG_FRUSTRATION)
        reasons.append("Strong frustration combined with a concrete unresolved problem.")

    if not knowledge_available and not answered and is_inquiry(user_input):
        signals.append(KNOWLEDGE_UNAVAILABLE)
        reasons.append("AI cannot safely answer: no grounded knowledge is available.")

    if not signals:
        return build_escalation_decision(should_escalate=False, category=category)

    confidence = max(SIGNAL_CONFIDENCE[s] for s in signals)
    return build_escalation_decision(
        should_escalate=True,
        reason=" ".join(reasons).strip(),
        confidence=confidence,
        priority=priority_for(category),
        signals=signals,
        summary=_build_summary(signals, user_input),
        category=category,
    )
