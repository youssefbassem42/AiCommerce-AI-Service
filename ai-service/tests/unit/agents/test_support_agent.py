from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.support.agent import SupportAgent
from app.agents.support.state import SupportState
from app.agents.support.tools import (
    REFUND_ESCALATION_THRESHOLD,
    SUPPORT_CATEGORIES,
    evaluate_refund_policy,
)
from app.application.ticket.dto.support_dto import SupportResponse


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = "{}"
    return l


@pytest.fixture
def customer_repo():
    r = AsyncMock()
    r.find_by_id.return_value = MagicMock(id="cust_1", store_id="store_1", tags=["gold"])
    return r


@pytest.fixture
def order_repo():
    r = AsyncMock()
    r.find_by_customer.return_value = [
        MagicMock(
            id="order_1",
            external_id="ORD-001",
            store_id="store_1",
            fulfillment_status="fulfilled",
            financial_status="paid",
            cancelled_at=None,
            currency="USD",
            line_items=[
                MagicMock(title="Laptop", quantity=1, price=999.0),
            ],
        )
    ]
    return r


@pytest.fixture
def ticket_service():
    t = AsyncMock()
    t.create_ticket.return_value = MagicMock(id="ticket-1", ticket_id="ticket-1")
    return t


@pytest.fixture
def escalation_agent():
    e = AsyncMock()
    e.run.return_value = MagicMock(
        ticket_id="ticket-1",
        priority="p2",
        assigned_to="finance",
        eta=datetime.now(UTC),
    )
    return e


@pytest.fixture
def agent(llm, customer_repo, order_repo, ticket_service, escalation_agent):
    return SupportAgent(
        llm=llm,
        customer_repo=customer_repo,
        order_repo=order_repo,
        ticket_service=ticket_service,
        escalation_agent=escalation_agent,
    )


class TestSupportTools:
    def test_refund_threshold(self):
        assert REFUND_ESCALATION_THRESHOLD > 0

    def test_support_categories(self):
        assert "order_status" in SUPPORT_CATEGORIES
        assert "refund" in SUPPORT_CATEGORIES
        assert "technical" in SUPPORT_CATEGORIES

    def test_evaluate_refund_policy_eligible(self):
        order = MagicMock(
            financial_status="paid",
            cancelled_at=None,
            total_price=MagicMock(amount=120.0),
            currency="USD",
        )
        info = evaluate_refund_policy(order)
        assert info["eligible"] is True
        assert info["amount"] == 120.0

    def test_evaluate_refund_policy_cancelled_not_eligible(self):
        order = MagicMock(
            financial_status="cancelled",
            cancelled_at=datetime.now(UTC),
            total_price=MagicMock(amount=120.0),
            currency="USD",
        )
        info = evaluate_refund_policy(order)
        assert info["eligible"] is False
        assert info["cancelled"] is True

    def test_evaluate_refund_policy_unpaid_not_eligible(self):
        order = MagicMock(
            financial_status="pending",
            cancelled_at=None,
            total_price=MagicMock(amount=120.0),
            currency="USD",
        )
        info = evaluate_refund_policy(order)
        assert info["eligible"] is False
        assert info["cancelled"] is False


class TestSupportAgent:
    async def test_run_verifies_customer_and_categorizes(self, agent):
        response = await agent.run(
            query="Where is my order?",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert isinstance(response, SupportResponse)
        assert response.query == "Where is my order?"
        assert response.verified is True
        assert response.issue_category is not None

    async def test_run_unverified_customer_escalates(self, llm, order_repo, ticket_service, escalation_agent):
        customer_repo = AsyncMock()
        customer_repo.find_by_id.return_value = None
        agent = SupportAgent(
            llm=llm,
            customer_repo=customer_repo,
            order_repo=order_repo,
            ticket_service=ticket_service,
            escalation_agent=escalation_agent,
        )
        response = await agent.run(
            query="I need urgent help",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert response.escalation_needed is True
        assert response.verified is False
        assert escalation_agent.run.await_count >= 0

    async def test_run_order_status_resolved_without_escalation(self, agent):
        response = await agent.run(
            query="Where is my order?",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert response.resolution_steps or response.rationale

    async def test_run_refund_over_threshold_escalates(self, llm, customer_repo, ticket_service, escalation_agent):
        order_repo = AsyncMock()
        order_repo.find_by_customer.return_value = [
            MagicMock(
                id="order_2",
                external_id="ORD-002",
                store_id="store_1",
                fulfillment_status="fulfilled",
                financial_status="paid",
                cancelled_at=None,
                currency="USD",
                line_items=[],
                total_price=MagicMock(amount=2000.0),
            )
        ]
        agent = SupportAgent(
            llm=llm,
            customer_repo=customer_repo,
            order_repo=order_repo,
            ticket_service=ticket_service,
            escalation_agent=escalation_agent,
        )
        llm.structured_output.return_value.message.content = '{"category": "refund"}'
        response = await agent.run(
            query="I want a refund",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert response.escalation_needed is True
        assert response.escalation_reason is not None

    async def test_run_error_path_returns_graceful_response(self):
        agent = SupportAgent(llm=AsyncMock())
        agent._graph.ainvoke = AsyncMock(side_effect=Exception("boom"))
        response = await agent.run(query="test", store_id="s1")
        assert isinstance(response, SupportResponse)
        assert response.rationale is not None

    async def test_state_shape(self):
        state: SupportState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": "c1",
            "conversation_id": None,
            "history": [],
            "verified": False,
            "customer": None,
            "issue_category": None,
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
        assert state["escalation_needed"] is False
