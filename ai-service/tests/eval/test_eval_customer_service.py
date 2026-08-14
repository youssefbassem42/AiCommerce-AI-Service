"""Phase 10 eval — Customer service scenarios.

Scenarios (real LLM, mocked repos):
- return
- shipping
- warranty
- product specs
- unknown question
"""

import pytest

from app.agents.support.agent import SupportAgent
from app.application.ticket.dto.support_dto import SupportResponse
from tests.eval.conftest import assert_latency

pytestmark = [pytest.mark.eval, pytest.mark.slow, pytest.mark.timeout(300)]


def _agent(
    llm,
    customer_repo,
    order_repo,
    ticket_service,
    escalation_agent,
    retriever_service,
    product_repo,
) -> SupportAgent:
    return SupportAgent(
        llm=llm,
        customer_repo=customer_repo,
        order_repo=order_repo,
        ticket_service=ticket_service,
        escalation_agent=escalation_agent,
        retriever_service=retriever_service,
        product_repo=product_repo,
    )


class TestCustomerServiceEval:
    async def test_eval_cs_return(
        self, llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
    ):
        """'return' — must answer from the return policy facts."""
        resp: SupportResponse = await _agent(
            llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
        ).run(
            query="What is your return policy? Can I return items?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected an answer"
        text = (resp.rationale or "").lower()
        assert "30" in text and "days" in text, "must state the 30-day window"
        assert resp.escalation_needed is False, "simple return question must not escalate"

    async def test_eval_cs_shipping(
        self, llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
    ):
        """'shipping' — must answer from the shipping policy facts."""
        resp = await _agent(
            llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
        ).run(
            query="How long does shipping take?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected an answer"
        text = (resp.rationale or "").lower()
        assert "3" in text and "5" in text and "days" in text, "must state the shipping window"
        assert resp.escalation_needed is False

    async def test_eval_cs_warranty(
        self, llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
    ):
        """'warranty' — must answer from the warranty facts."""
        resp = await _agent(
            llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
        ).run(
            query="Do your laptops come with a warranty?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected an answer"
        text = (resp.rationale or "").lower()
        assert "12" in text and "month" in text, "must state the warranty duration"
        assert resp.escalation_needed is False

    async def test_eval_cs_product_specs(
        self, llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
    ):
        """'product specs' — must answer from catalog/product facts."""
        resp = await _agent(
            llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
        ).run(
            query="Tell me about the products you sell — what specs do your laptops have?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected an answer"
        assert resp.escalation_needed is False

    async def test_eval_cs_unknown_question(
        self, llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
    ):
        """'unknown question' — honest non-answer: no invented policy, honest fallback."""
        resp = await _agent(
            llm, customer_repo, order_repo, ticket_service, escalation_agent, retriever_service, product_repo
        ).run(
            query="What is the exact chemical composition of your fabric dyes?",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.rationale, "expected a response"
        text = (resp.rationale or "").lower()
        assert any(
            marker in text
            for marker in ("don't have", "do not have", "don't know", "do not know", "not available", "support team")
        ), "must honestly decline instead of inventing an answer"
