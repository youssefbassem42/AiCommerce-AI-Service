"""Phase 10 eval — Memory scenarios (multi-turn constraints).

Verifies that a preference stored in session memory constrains a later
recommendation turn in the same session (budget remembered across turns).
"""

import pytest

from app.agents.memory.agent import MemoryAgent
from app.agents.recommendation.agent import RecommendationAgent
from tests.eval.conftest import assert_latency

pytestmark = [pytest.mark.eval, pytest.mark.slow, pytest.mark.timeout(300)]


class TestMemoryEval:
    async def test_eval_memory_multi_turn_budget(self, llm, memory_repo, retriever_service, product_repo):
        """Turn 1 stores a budget preference; turn 2 must honor it."""
        memory = MemoryAgent(memory_repo=memory_repo, llm=llm)

        stored = await memory.store(
            key="preferences",
            session_id="sess-1",
            user_id="cust-eval",
            store_id="store-eval",
            value={"max_budget": 800.0, "product_type": "laptop"},
        )
        assert stored.get("error") is None, f"store failed: {stored.get('error')}"

        recalled = await memory.recall(
            session_id="sess-1",
            user_id="cust-eval",
            store_id="store-eval",
        )
        prefs = (recalled.get("retrieved") or {}).get("value") or {}
        assert float(prefs.get("max_budget", 0)) == 800.0, "preference must survive store -> recall"

        agent = RecommendationAgent(
            retriever_service=retriever_service,
            product_repo=product_repo,
            llm=llm,
        )
        resp = await agent.run(
            query="What about the cheaper option?",
            store_id="store-eval",
            customer_id="cust-eval",
            shopping_state={
                "memory": {"preferences": prefs},
                "product_type": "laptop",
            },
        )
        assert_latency(resp)
        assert resp.products, "expected products constrained by remembered preference"
        for product in resp.products:
            assert float(product.price) <= 800.0, "multi-turn budget constraint must be honored"

    async def test_eval_memory_forget(self, llm, memory_repo):
        """Forgotten preferences must not surface on recall."""
        memory = MemoryAgent(memory_repo=memory_repo, llm=llm)
        await memory.store(
            key="preferences",
            session_id="sess-2",
            user_id="cust-eval",
            store_id="store-eval",
            value={"max_budget": 300.0},
        )
        forgotten = await memory.forget(
            key="preferences",
            session_id="sess-2",
            user_id="cust-eval",
            store_id="store-eval",
        )
        assert forgotten.get("error") is None
        recalled = await memory.recall(
            session_id="sess-2",
            user_id="cust-eval",
            store_id="store-eval",
        )
        assert recalled.get("retrieved") is None, "forgotten preference must not be recalled"