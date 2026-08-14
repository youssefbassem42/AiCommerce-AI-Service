"""Canonical escalation decision structure.

Captures whether a turn should hand off to a human agent and why, so every
path (conversation workflow, support agent, RAG service) emits the same
decision shape. Escalation is the last resort: it must be justified by one
or more explicit signals, never by identity (customer_id == null) or by the
mere fact that the customer asked a support question.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EscalationDecision(BaseModel):
    should_escalate: bool = False
    reason: str | None = Field(default=None, description="Why this turn is being escalated to a human")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="How confident the decision is")
    priority: str | None = Field(default=None, description="P1-P4 priority for the handoff")
    signals: list[str] = Field(
        default_factory=list,
        description="The signals that triggered this decision (e.g. 'explicit_human_request')",
    )
    summary: str | None = Field(default=None, description="Short handoff summary for the human agent")
    category: str | None = None
    ticket_id: str | None = None
    assigned_to: str | None = None
    eta: str | None = None


def build_escalation_decision(
    *,
    should_escalate: bool = False,
    reason: str | None = None,
    confidence: float = 0.0,
    priority: str | None = None,
    signals: list[str] | None = None,
    summary: str | None = None,
    category: str | None = None,
    ticket_id: str | None = None,
    assigned_to: str | None = None,
    eta: Any = None,
) -> EscalationDecision:
    return EscalationDecision(
        should_escalate=should_escalate,
        reason=reason,
        confidence=max(0.0, min(1.0, confidence)),
        priority=priority,
        signals=list(signals or []),
        summary=summary,
        category=category,
        ticket_id=ticket_id,
        assigned_to=assigned_to,
        eta=str(eta) if eta is not None else None,
    )
