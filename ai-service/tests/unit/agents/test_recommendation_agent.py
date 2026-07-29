import pytest
from unittest.mock import AsyncMock

from app.agents.recommendation.agent import RecommendationAgent
from app.agents.recommendation.state import RecommendationState
from app.application.recommendation.dto.recommendation_dto import (
    ProductCard,
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)


@pytest.fixture
def retriever():
    r = AsyncMock()
    r.search.return_value.results = []
    return r


@pytest.fixture
def product_repo():
    r = AsyncMock()
    r.find_by_id.return_value = None
    return r


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = (
        '{"product_type": "laptop", "use_case": "gaming", '
        '"required_specs": [], "max_budget": 1500.0, '
        '"min_quality": null, "hidden_needs": []}'
    )
    return l


@pytest.fixture
def agent(retriever, product_repo, llm):
    return RecommendationAgent(
        retriever_service=retriever,
        product_repo=product_repo,
        llm=llm,
    )


class TestRecommendationAgent:
    async def test_run_returns_response(self, agent):
        response = await agent.run(
            query="gaming laptop",
            store_id="store_1",
            customer_id="customer_1",
        )
        assert isinstance(response, RecommendationResponse)
        assert response.query == "gaming laptop"
        assert response.store_id == "store_1"
        assert response.customer_id == "customer_1"

    async def test_run_empty_query_still_returns_response(self, agent, llm):
        llm.structured_output.return_value.message.content = (
            '{"product_type": null, "use_case": null, '
            '"required_specs": [], "max_budget": null, '
            '"min_quality": null, "hidden_needs": []}'
        )
        response = await agent.run(
            query="",
            store_id="store_1",
        )
        assert isinstance(response, RecommendationResponse)
        assert response.total_count == 0

    async def test_route_after_intent_error_sends_to_format(self, agent):
        from app.agents.recommendation.agent import route_after_intent
        state: RecommendationState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "intent": None,
            "candidates": [],
            "filtered": [],
            "response": None,
            "error": "Something went wrong",
        }
        assert route_after_intent(state) == "format_response"

    async def test_route_after_search_empty(self, agent):
        from app.agents.recommendation.agent import route_after_search
        state: RecommendationState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "intent": RecommendationIntent(product_type="laptop"),
            "candidates": [],
            "filtered": [],
            "response": None,
            "error": None,
        }
        assert route_after_search(state) == "format_response"

    async def test_route_after_search_has_candidates(self, agent):
        from app.agents.recommendation.agent import route_after_search
        state: RecommendationState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "intent": RecommendationIntent(product_type="laptop"),
            "candidates": [ScoredProduct(product_id="p1", title="P1", store_id="s1")],
            "filtered": [],
            "response": None,
            "error": None,
        }
        assert route_after_search(state) == "filter_inventory"
