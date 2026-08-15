from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.agents.recommendation.agent import RecommendationAgent
from app.agents.recommendation.state import RecommendationState
from app.application.recommendation.dto.recommendation_dto import (
    RecommendationIntent,
    RecommendationResponse,
    ScoredProduct,
)
from app.domain.commerce.aggregates.product import Variant
from app.domain.commerce.value_objects.money import Money


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

    async def test_run_applies_intent_budget_and_price(self, agent, product_repo):
        from app.domain.commerce.aggregates.product import Product

        product_repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="Laptop",
            variants=[Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("1200")))],
        )
        product_repo.find_by_id.return_value.variants[0].inventory_quantity = 3

        from app.agents.recommendation.nodes import filter_inventory_node

        state: RecommendationState = {
            "user_query": "gaming laptop",
            "store_id": "s1",
            "customer_id": None,
            "intent": RecommendationIntent(product_type="laptop", max_budget=1500.0),
            "candidates": [ScoredProduct(product_id="p1", title="Laptop", store_id="s1")],
            "filtered": [],
            "response": None,
            "error": None,
        }
        out = await filter_inventory_node(state, product_repo)
        assert len(out["filtered"]) == 1
        assert out["filtered"][0].price == 1200.0

    async def test_run_drops_above_budget(self, agent, product_repo):
        from app.domain.commerce.aggregates.product import Product

        product_repo.find_by_id.return_value = Product(
            id="p1",
            store_id="s1",
            organization_id="o1",
            title="Laptop",
            variants=[Variant(id="v1", sku="S1", title="V1", price=Money(amount=Decimal("2000")))],
        )
        product_repo.find_by_id.return_value.variants[0].inventory_quantity = 3

        from app.agents.recommendation.nodes import filter_inventory_node

        state: RecommendationState = {
            "user_query": "gaming laptop",
            "store_id": "s1",
            "customer_id": None,
            "shopping_state": None,
            "intent": RecommendationIntent(product_type="laptop", max_budget=1500.0),
            "candidates": [ScoredProduct(product_id="p1", title="Laptop", store_id="s1")],
            "filtered": [],
            "clarifying_question": None,
            "response": None,
            "error": None,
        }
        out = await filter_inventory_node(state, product_repo)
        assert out["filtered"] == []


class TestRecommendationShoppingState:
    """Multi-turn state must reach the search without the user repeating anything (Fix 3.5)."""

    @pytest.fixture
    def shopping_llm(self):
        provider = AsyncMock()
        provider.structured_output.return_value.message.content = (
            '{"product_type": null, "use_case": null, "required_specs": [], '
            '"max_budget": null, "min_quality": null, "hidden_needs": []}'
        )
        return provider

    async def test_state_fills_budget_and_use_case(self, retriever, product_repo, shopping_llm):
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="Programming",
            store_id="s1",
            shopping_state={
                "intent": "product_recommendation",
                "category": "laptop",
                "budget": 800,
                "currency": "USD",
                "color": None,
                "size": None,
                "brand": None,
                "use_case": "programming",
            },
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "laptop" in search_query
        assert "programming" in search_query
        assert response.clarifying_question is None

    async def test_terse_reply_searches_with_recalled_state(self, retriever, product_repo, shopping_llm):
        """'$800' after 'What's your budget?' — state already carries category + budget."""
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="$800",
            store_id="s1",
            shopping_state={
                "intent": "product_recommendation",
                "category": "laptop",
                "budget": 800,
                "use_case": "programming",
            },
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "laptop" in search_query
        assert "programming" in search_query
        assert response.clarifying_question is None

    async def test_state_color_becomes_required_spec(self, retriever, product_repo, shopping_llm):
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="Black",
            store_id="s1",
            shopping_state={
                "intent": "product_recommendation",
                "category": "dress",
                "budget": 50,
                "color": "black",
                "use_case": "party",
            },
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "dress" in search_query
        assert "black" in search_query
        assert response.clarifying_question is None

    async def test_missing_budget_asks_clarifying_question(self, retriever, product_repo, shopping_llm):
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="I need a laptop",
            store_id="s1",
            shopping_state={"intent": "product_recommendation", "category": "laptop"},
        )

        assert response.clarifying_question is not None
        assert "budget" in response.clarifying_question.lower()
        assert response.products == []
        retriever.search.assert_not_awaited()

    async def test_missing_use_case_searches_after_budget_known(self, retriever, product_repo, shopping_llm):
        """Use case is a soft ranking signal, never a blocking question."""
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="$800",
            store_id="s1",
            shopping_state={"intent": "product_recommendation", "category": "laptop", "budget": 800},
        )

        assert response.clarifying_question is None
        assert response.products is not None

    async def test_complete_state_searches_directly(self, retriever, product_repo, shopping_llm):
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="Programming",
            store_id="s1",
            shopping_state={
                "intent": "product_recommendation",
                "category": "laptop",
                "budget": 800,
                "use_case": "programming",
            },
        )

        assert retriever.search.await_count == 1
        assert response.clarifying_question is None

    async def test_current_message_overrides_recalled_category(self, retriever, product_repo, shopping_llm):
        shopping_llm.structured_output.return_value.message.content = (
            '{"product_type": "desktop", "use_case": "gaming", "required_specs": [], '
            '"max_budget": null, "min_quality": null, "hidden_needs": []}'
        )
        agent = RecommendationAgent(retriever_service=retriever, product_repo=product_repo, llm=shopping_llm)

        response = await agent.run(
            query="Actually I changed my mind, a desktop",
            store_id="s1",
            shopping_state={"intent": "product_recommendation", "category": "laptop", "budget": 800},
        )

        search_query = retriever.search.await_args.kwargs["query"]
        assert "desktop" in search_query
        assert "laptop" not in search_query
        assert response.clarifying_question is None
