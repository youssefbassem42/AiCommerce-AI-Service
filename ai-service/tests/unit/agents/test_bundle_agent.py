from unittest.mock import AsyncMock

import pytest

from app.agents.bundle.agent import (
    BundleSuggestionAgent,
    route_after_budget,
    route_after_candidates,
)
from app.agents.bundle.state import BundleState
from app.application.recommendation.dto.recommendation_dto import BundleResponse


@pytest.fixture
def product_repo():
    r = AsyncMock()
    r.find_many.return_value = []
    return r


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = (
        '{"budget": 300.0, "desired_items": ["monitor"], "use_case": "office"}'
    )
    return l


@pytest.fixture
def agent(product_repo, llm):
    return BundleSuggestionAgent(product_repo=product_repo, llm=llm)


class TestBundleSuggestionAgent:
    async def test_run_returns_response(self, agent):
        response = await agent.run(
            query="I have $300 and want a monitor",
            store_id="store_1",
            customer_id="cust_1",
        )
        assert isinstance(response, BundleResponse)
        assert response.query == "I have $300 and want a monitor"
        assert response.store_id == "store_1"
        assert response.customer_id == "cust_1"

    async def test_run_no_budget_parsed(self, agent, llm):
        llm.structured_output.return_value.message.content = '{"budget": null, "desired_items": [], "use_case": null}'
        response = await agent.run(
            query="I want something",
            store_id="store_1",
        )
        assert isinstance(response, BundleResponse)

    async def test_route_after_budget_no_items(self):
        state: BundleState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "budget": None,
            "desired_items": [],
            "budget_parsed": False,
            "candidates_by_type": {},
            "bundles": [],
            "selected": [],
            "promo_code": None,
            "response": None,
            "error": "Failed",
        }
        assert route_after_budget(state) == "format_response"

    async def test_route_after_budget_has_items(self):
        state: BundleState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "budget": 300.0,
            "desired_items": ["monitor"],
            "budget_parsed": True,
            "candidates_by_type": {},
            "bundles": [],
            "selected": [],
            "promo_code": None,
            "response": None,
            "error": None,
        }
        assert route_after_budget(state) == "find_candidates"

    async def test_route_after_candidates_empty(self):
        state: BundleState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "budget": 300.0,
            "desired_items": ["monitor"],
            "budget_parsed": True,
            "candidates_by_type": {},
            "bundles": [],
            "selected": [],
            "promo_code": None,
            "response": None,
            "error": None,
        }
        assert route_after_candidates(state) == "format_response"
