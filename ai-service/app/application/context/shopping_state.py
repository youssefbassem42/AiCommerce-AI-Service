"""Structured shopping state for multi-turn conversations (Phase 3).

The state is short-term conversation memory (session-scoped), merged
incrementally on every message:

    message
     ↓
    load conversation
     ↓
    recall memory
     ↓
    merge constraints
     ↓
    understand current message

It is deliberately kept separate from long-term user memory (Fix 3.4):
session state holds the current shopping goal ("dress", "$50", "black"),
while user memory holds durable preferences ("prefers black").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SESSION_STATE_KEY = "shopping_state"

_STATE_FIELDS = (
    "intent",
    "category",
    "budget",
    "currency",
    "color",
    "size",
    "brand",
    "use_case",
)

# Fields that only describe the current product; cleared when the category changes.
_CATEGORY_SCOPED_FIELDS = ("color", "size", "brand", "use_case")

_DISPLAY_NAMES = {
    "intent": "intent",
    "category": "product type",
    "budget": "budget",
    "currency": "currency",
    "color": "color",
    "size": "size",
    "brand": "brand",
    "use_case": "use case",
}


@dataclass
class ShoppingState:
    """Incremental requirements gathered across a conversation."""

    intent: str | None = None
    category: str | None = None
    budget: float | None = None
    currency: str | None = None
    color: str | None = None
    size: str | None = None
    brand: str | None = None
    use_case: str | None = None
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ShoppingState:
        if not data:
            return cls()
        known = {f: data.get(f) for f in _STATE_FIELDS}
        return cls(
            intent=_clean_str(known["intent"]),
            category=_clean_str(known["category"]),
            budget=_clean_budget(known["budget"]),
            currency=_clean_str(known["currency"]),
            color=_clean_str(known["color"]),
            size=_clean_str(known["size"]),
            brand=_clean_str(known["brand"]),
            use_case=_clean_str(known["use_case"]),
            _extra={k: v for k, v in data.items() if k not in _STATE_FIELDS},
        )

    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in _STATE_FIELDS}

    def is_empty(self) -> bool:
        return all(getattr(self, f) is None for f in _STATE_FIELDS)

    def merge(self, update: dict[str, Any] | ShoppingState | None) -> ShoppingState:
        """Overlay newer information on top of this state (new values win).

        When the category changes, fields that only describe the previous
        product (color, size, brand, use case) are reset so stale constraints
        never leak into a new shopping goal.
        """
        incoming = update if isinstance(update, ShoppingState) else ShoppingState.from_dict(update)
        if incoming.is_empty():
            return self

        merged = ShoppingState.from_dict(self.to_dict())

        if incoming.category is not None and incoming.category != self.category:
            for field_name in _CATEGORY_SCOPED_FIELDS:
                setattr(merged, field_name, None)

        for field_name in _STATE_FIELDS:
            new_value = getattr(incoming, field_name)
            if new_value is not None:
                setattr(merged, field_name, new_value)

        return merged

    def missing_requirements(self) -> list[str]:
        """Unanswered requirements, in the order the assistant should ask."""
        missing: list[str] = []
        if not self.category:
            missing.append("category")
        if self.budget is None:
            missing.append("budget")
        if not self.use_case:
            missing.append("use_case")
        return missing

    def to_prompt_text(self) -> str:
        """Human-readable rendering for prompts, e.g. "product type=laptop, budget=800, color=black"."""
        parts = []
        for field_name in _STATE_FIELDS:
            value = getattr(self, field_name)
            if value is None:
                continue
            parts.append(f"{_DISPLAY_NAMES[field_name]}={value}")
        return ", ".join(parts)


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none"):
        return None
    return text


def _clean_budget(value: Any) -> float | None:
    if value is None:
        return None
    try:
        budget = float(value)
    except (TypeError, ValueError):
        return None
    if budget <= 0:
        return None
    return budget


def shopping_state_from_context(context: dict[str, Any] | None) -> ShoppingState:
    """Extract the shopping state from the canonical AIContext dict.

    Precedence: explicit conversation state, then recalled memory entries.
    """
    context = context or {}
    conversation = context.get("conversation") or {}
    conversation_state = conversation.get(SESSION_STATE_KEY)
    if conversation_state:
        return ShoppingState.from_dict(conversation_state)

    memory = context.get("memory") or {}
    entries = memory.get("entries") or (memory if "entries" not in memory else {})
    if isinstance(entries, dict) and entries.get(SESSION_STATE_KEY):
        return ShoppingState.from_dict(entries[SESSION_STATE_KEY])

    return ShoppingState()
