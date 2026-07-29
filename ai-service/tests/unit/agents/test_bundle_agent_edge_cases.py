from unittest.mock import AsyncMock

import pytest

from app.agents.bundle.agent import BundleSuggestionAgent
from app.agents.bundle.state import BundleState
from app.application.recommendation.dto.recommendation_dto import BundleResponse
from app.application.recommendation.promo_service import PromoCodeService


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


class TestBundleAgentPromoDisabled:
    async def test_agent_runs_without_promo_service(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=None)
        response = await agent.run(query="I have $300 and want a monitor", store_id="store_1")
        assert isinstance(response, BundleResponse)
        assert response.promo_code is None

    async def test_graph_skips_promo_node_when_disabled(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=None)
        assert agent._promo_enabled is False
        graph = agent._graph
        nodes = list(graph.nodes.keys())
        assert "handle_promo" not in nodes

    async def test_graph_includes_promo_node_when_enabled(self, product_repo, llm):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value="BUNDLE-TEST123")
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=promo)
        assert agent._promo_enabled is True
        graph = agent._graph
        nodes = list(graph.nodes.keys())
        assert "handle_promo" in nodes

    async def test_promo_disabled_returns_no_code_in_response(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=None)
        response = await agent.run(query="I have $300 and want a monitor", store_id="store_1")
        assert response.promo_code is None

    async def test_agent_with_promo_enabled(self, product_repo, llm):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value="BUNDLE-TEST123")
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=promo)
        response = await agent.run(query="I have $300 and want a monitor", store_id="store_1")
        assert isinstance(response, BundleResponse)

    async def test_routing_after_select_respects_promo_flag(self, product_repo, llm):
        from app.agents.bundle.agent import route_after_select

        state: BundleState = {
            "user_query": "test",
            "store_id": "s1",
            "customer_id": None,
            "budget": 300.0,
            "desired_items": ["monitor"],
            "budget_parsed": True,
            "candidates_by_type": {},
            "bundles": [],
            "selected": [AsyncMock()],
            "promo_code": None,
            "response": None,
            "error": None,
            "store_capabilities": {"has_promo_codes": True},
        }
        assert route_after_select(state) == "handle_promo"


class TestBundleAgentEdgeCases:
    async def test_empty_user_query(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="", store_id="store_1")
        assert isinstance(response, BundleResponse)

    async def test_run_without_store_id(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I need a monitor", store_id="")
        assert isinstance(response, BundleResponse)

    async def test_intent_parse_failure_returns_fallback(self, product_repo, llm):
        llm.structured_output.side_effect = Exception("LLM unavailable")
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I have $300 and want a monitor", store_id="store_1", customer_id="cust_1")
        assert isinstance(response, BundleResponse)
        assert response.budget == 0.0
        assert response.promo_code is None

    async def test_no_products_found(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I have $300 and want a monitor", store_id="store_1")
        assert isinstance(response, BundleResponse)
        assert "No bundles found" in (response.rationale or "")

    async def test_budget_zero(self, product_repo, llm):
        llm.structured_output.return_value.message.content = (
            '{"budget": 0.0, "desired_items": ["monitor"], "use_case": null}'
        )
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I want a free monitor", store_id="store_1")
        assert isinstance(response, BundleResponse)
