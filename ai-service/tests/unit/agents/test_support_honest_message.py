"""Phase 0: support format node must not claim a fake specialist transfer."""

import pytest

from app.agents.support.nodes import format_support_response_node
from app.agents.support.state import SupportState


def _state(**overrides) -> SupportState:
    state: SupportState = {
        "user_query": "where is my order",
        "store_id": "store-1",
        "customer_id": None,
        "conversation_id": None,
        "history": [],
        "verified": False,
        "customer": None,
        "issue_category": "general",
        "order": None,
        "order_matches": [],
        "resolution_steps": [],
        "refund_info": None,
        "escalation_needed": False,
        "escalation_reason": None,
        "ticket_id": None,
        "priority": None,
        "assigned_to": None,
        "eta": None,
        "satisfaction_question": None,
        "response": None,
        "error": None,
    }
    state.update(overrides)
    return state


class TestSupportHonestMessage:
    @pytest.mark.asyncio
    async def test_general_unresolved_does_not_claim_transfer(self):
        result = await format_support_response_node(_state())
        response = result["response"]

        assert "transfer" not in response.rationale.lower()
        assert "specialist" not in response.rationale.lower()
        assert "Transferred to a human specialist" not in response.resolution_steps
        assert response.escalation_needed is False
        assert response.ticket_id is None
        assert "contact the store's support team" in response.rationale

    @pytest.mark.asyncio
    async def test_general_with_steps_keeps_existing_behavior(self):
        result = await format_support_response_node(_state(resolution_steps=["Check the email for tracking."]))
        response = result["response"]
        assert response.rationale == "Check the email for tracking."
        assert response.resolution_steps == ["Check the email for tracking."]

    @pytest.mark.asyncio
    async def test_escalation_path_still_mentions_handoff(self):
        result = await format_support_response_node(
            _state(
                escalation_needed=True,
                escalation_reason="refund dispute",
                ticket_id="t-9",
                priority="high",
                assigned_to="support",
                persistence_success=True,
            )
        )
        response = result["response"]
        assert response.escalation_needed is True
        assert response.ticket_id == "t-9"
        assert "handing this over" in response.rationale.lower()
