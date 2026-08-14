"""Phase 10 eval — Recommendation scenarios.

Scenarios (real LLM, mocked catalog):
- dress
- dress + $50
- laptop
- laptop + $800
- laptop + programming
"""

import pytest

from app.agents.recommendation.agent import RecommendationAgent
from tests.eval.conftest import assert_latency

pytestmark = [pytest.mark.eval, pytest.mark.slow, pytest.mark.timeout(300)]


def _agent(llm, retriever_service, product_repo) -> RecommendationAgent:
    return RecommendationAgent(
        retriever_service=retriever_service,
        product_repo=product_repo,
        llm=llm,
    )


def _price_of(product) -> float:
    return float(product.price.amount)


class TestRecommendationEval:
    async def test_eval_rec_dress(self, llm, retriever_service, product_repo, catalog):
        """'dress' — must surface dress products with rationale."""
        resp = await _agent(llm, retriever_service, product_repo).run(
            query="I'm looking for a dress", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.products, "expected dress recommendations"
        assert all("dress" in (p.title or "").lower() for p in resp.products), "only dress products expected"
        assert resp.rationale, "rationale must explain the picks"

    async def test_eval_rec_dress_budget_50(self, llm, retriever_service, product_repo):
        """'dress + $50' — budget must be honored (<= $50)."""
        resp = await _agent(llm, retriever_service, product_repo).run(
            query="show me dresses under $50", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.products, "expected at least one dress within budget"
        assert all(_price_of(p) <= 50.0 for p in resp.products), "every product must fit the budget"

    async def test_eval_rec_laptop(self, llm, retriever_service, product_repo):
        """'laptop' — must return laptop products only."""
        resp = await _agent(llm, retriever_service, product_repo).run(
            query="recommend a laptop", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.products, "expected laptop recommendations"
        assert all("laptop" in (p.title or "").lower() for p in resp.products)

    async def test_eval_rec_laptop_budget_800(self, llm, retriever_service, product_repo):
        """'laptop + $800' — no product may exceed $800."""
        resp = await _agent(llm, retriever_service, product_repo).run(
            query="laptop for work, max budget $800", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.products, "expected a laptop within $800"
        assert all(_price_of(p) <= 800.0 for p in resp.products), "budget must be honored"

    async def test_eval_rec_laptop_programming(self, llm, retriever_service, product_repo):
        """'laptop + programming' — use-case constraint must shape the picks."""
        resp = await _agent(llm, retriever_service, product_repo).run(
            query="a laptop for programming and development", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.products, "expected laptop recommendations for programming"
        assert all("laptop" in (p.title or "").lower() for p in resp.products)
        assert resp.rationale, "rationale should explain suitability for programming"
