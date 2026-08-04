from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.sales.agent import SalesAgent
from app.agents.sales.state import SalesState
from app.application.recommendation.dto.recommendation_dto import ProductCard
from app.application.recommendation.dto.sales_dto import SalesResponse


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = "{}"
    return l


@pytest.fixture
def recommendation_service():
    r = AsyncMock()
    r.recommend.return_value = MagicMock(
        query="test",
        store_id="store_1",
        customer_id="cust_1",
        products=[
            ProductCard(
                product_id="p1",
                title="Laptop",
                price=999.0,
                currency="USD",
                score=0.95,
                source="catalog",
            )
        ],
        suggestions=[],
        rationale=None,
        latency_ms=0.0,
    )
    return r


@pytest.fixture
def promo_service():
    p = AsyncMock()
    p.generate_code.return_value = MagicMock(
        code="SALES-ABC123",
        discount_pct=10.0,
        valid_until=None,
    )
    return p


@pytest.fixture
def agent(llm, recommendation_service, promo_service):
    return SalesAgent(
        llm=llm,
        recommendation_service=recommendation_service,
        promo_service=promo_service,
    )


class TestSalesAgent:
    async def test_run_returns_sales_response(self, agent):
        llm = agent._llm
        llm.structured_output.return_value.message.content = (
            '{"budget": 1000, "use_case": "office", "preferences": ["laptop"], '
            '"has_enough_info": true, "clarifying_question": null}'
        )
        response = await agent.run(
            query="I have $1000 and want a laptop for office work",
            store_id="store_1",
            customer_id="cust_1",
            store_capabilities={"has_promo_codes": True},
        )
        assert isinstance(response, SalesResponse)
        assert response.query == "I have $1000 and want a laptop for office work"
        assert response.store_id == "store_1"
        assert response.customer_id == "cust_1"
        assert response.stage in ("discovery", "qualification", "recommendation", "objection_handling", "close")

    async def test_run_asks_clarifying_question_when_info_missing(self, agent):
        llm = agent._llm
        llm.structured_output.return_value.message.content = (
            '{"budget": null, "use_case": null, "preferences": [], '
            '"has_enough_info": false, "clarifying_question": "What is your budget?"}'
        )
        response = await agent.run(query="I want something", store_id="store_1")
        assert isinstance(response, SalesResponse)
        assert response.clarifying_question == "What is your budget?"

    async def test_run_falls_back_on_llm_failure(self, agent):
        agent._llm.structured_output.side_effect = Exception("LLM down")
        response = await agent.run(query="I need a laptop", store_id="store_1", customer_id="cust_1")
        assert isinstance(response, SalesResponse)

    async def test_run_error_path_returns_graceful_response(self):
        agent = SalesAgent(llm=AsyncMock(), recommendation_service=None, promo_service=None)
        agent._graph.ainvoke = AsyncMock(side_effect=Exception("graph failure"))
        response = await agent.run(query="test", store_id="store_1")
        assert isinstance(response, SalesResponse)
        assert response.rationale is not None

    async def test_state_shape(self, agent):
        state: SalesState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": "c1",
            "conversation_id": None,
            "history": [],
            "stage": "discovery",
            "customer_answers": {},
            "products": [],
            "offer": {},
            "objection": None,
            "promo_code": None,
            "checkout_note": None,
            "clarifying_question": None,
            "store_capabilities": {},
            "response": None,
            "error": None,
        }
        assert state["stage"] == "discovery"
        assert state["products"] == []
