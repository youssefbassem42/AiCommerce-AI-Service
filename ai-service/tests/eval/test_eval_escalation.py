"""Phase 10 eval — Escalation scenarios.

Scenarios (real LLM, mocked repos):
- human request -> explicit escalation + ticket
- unknown answer -> knowledge-unavailable escalation (honest handoff)
- frustrated user -> strong frustration + problem -> escalation
- normal support -> no escalation
"""

import pytest

from app.agents.escalation.agent import EscalationAgent
from app.agents.support.agent import SupportAgent
from tests.eval.conftest import assert_latency

pytestmark = [pytest.mark.eval, pytest.mark.slow, pytest.mark.timeout(300)]


def _support(
    llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
) -> SupportAgent:
    escalation = EscalationAgent(
        llm=llm,
        ticket_service=ticket_service,
        notification_service=notification_service,
        customer_repo=customer_repo,
    )
    return SupportAgent(
        llm=llm,
        customer_repo=customer_repo,
        order_repo=order_repo,
        ticket_service=ticket_service,
        escalation_agent=escalation,
        retriever_service=retriever_service,
        product_repo=product_repo,
    )


class TestEscalationEval:
    async def test_eval_esc_human_request(
        self, llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
    ):
        """'human request' — explicit request to speak to a human must escalate."""
        resp = await _support(
            llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
        ).run(
            query="This is taking too long. I want to talk to a human agent now.",
            store_id="store-eval",
            customer_id="cust-eval",
            history=[
                {"role": "user", "content": "My order is late."},
                {"role": "assistant", "content": "Let me look into it."},
            ],
        )
        assert_latency(resp)
        assert resp.escalation_needed is True, "explicit human request must escalate"
        assert resp.ticket_id, "escalation must create a ticket"

    async def test_eval_esc_unknown_answer(
        self, llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
    ):
        """'unknown answer' — no grounded knowledge -> honest handoff to a human."""
        resp = await _support(
            llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
        ).run(
            query="Can I use a 110V appliance at 220V outlets, and is that covered?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected a response"
        if resp.escalation_needed:
            assert resp.ticket_id, "escalated turns must carry a ticket"
        else:
            text = (resp.rationale or "").lower()
            assert any(
                marker in text
                for marker in ("don't have", "do not have", "don't know", "not available", "support team")
            ), "non-escalated unknown answers must still decline honestly"

    async def test_eval_esc_frustrated_user(
        self, llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
    ):
        """'frustrated user' — strong frustration with a concrete problem escalates."""
        resp = await _support(
            llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
        ).run(
            query=(
                "I am FURIOUS. My order was supposed to arrive last week and it is STILL missing. "
                "This is unacceptable, I demand a full refund right now!"
            ),
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.escalation_needed is True, "strong frustration + concrete problem must escalate"
        assert resp.ticket_id, "escalation must create a ticket"

    async def test_eval_esc_normal_support(
        self, llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
    ):
        """'normal support' — routine question resolves without escalation."""
        resp = await _support(
            llm, customer_repo, order_repo, ticket_service, notification_service, retriever_service, product_repo
        ).run(
            query="How many days do I have to return an item?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.escalation_needed is False, "routine policy question must not escalate"
        assert resp.ticket_id is None, "no ticket for routine support"
