"""Canonical intent vocabulary for the AI service.

Single source of truth for intent strings used across coordinator routing,
sub-agents, and structured logging. Nothing else should hardcode intent
strings; import from here instead.
"""

from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    SALES = "sales"
    SUPPORT = "support"
    BUNDLE = "bundle"
    RECOMMENDATION = "recommendation"
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    ESCALATION = "escalation"
    INTEGRATION = "integration"
    GENERAL = "general"


# Intents that hand off to an executable conversational agent.
EXECUTABLE_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.BUNDLE,
        Intent.RECOMMENDATION,
        Intent.SALES,
        Intent.SUPPORT,
        Intent.ESCALATION,
    }
)

# Intents that exist in the routing table but have no executable agent yet.
COMING_SOON_INTENTS: frozenset[Intent] = frozenset({Intent.MARKETING, Intent.ANALYTICS})

# Intents handled by fallback/general answering (no dedicated agent).
FALLBACK_INTENTS: frozenset[Intent] = frozenset({Intent.INTEGRATION, Intent.GENERAL})


def coerce_intent(value: str | None) -> Intent | None:
    """Normalize an arbitrary LLM-provided intent string to the canonical enum."""
    if not value:
        return None
    try:
        return Intent(value.strip().lower())
    except ValueError:
        return None
