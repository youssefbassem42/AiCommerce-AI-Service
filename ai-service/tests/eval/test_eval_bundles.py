"""Phase 10 eval — Bundle scenarios.

Scenarios (real LLM, mocked catalog):
- mouse + keyboard
- mouse + keyboard + budget
- bundle + discount (promo code path)
"""

import pytest

from app.agents.bundle.agent import BundleSuggestionAgent
from tests.eval.conftest import assert_latency

pytestmark = [pytest.mark.eval, pytest.mark.slow, pytest.mark.timeout(300)]


def _agent(llm, product_repo, promo_service=None) -> BundleSuggestionAgent:
    return BundleSuggestionAgent(
        product_repo=product_repo,
        llm=llm,
        promo_service=promo_service,
    )


class TestBundleEval:
    async def test_eval_bundle_mouse_keyboard(self, llm, product_repo):
        """'mouse + keyboard' — complementary items must be bundled together."""
        resp = await _agent(llm, product_repo).run(
            query="I need a mouse and a keyboard for my new desk setup",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.bundles, "expected at least one bundle"
        bundle = resp.bundles[0]
        titles = " ".join(p.product_title for p in bundle.products).lower()
        assert "mouse" in titles and "keyboard" in titles, "bundle must contain mouse and keyboard"

    async def test_eval_bundle_mouse_keyboard_budget(self, llm, product_repo):
        """'mouse + keyboard + budget' — bundle total must respect the budget."""
        resp = await _agent(llm, product_repo).run(
            query="mouse and keyboard, budget $100", store_id="store-eval", customer_id="cust-eval"
        )
        assert_latency(resp)
        assert resp.bundles, "expected a bundle within budget"
        bundle = resp.bundles[0]
        assert bundle.within_budget, f"bundle must be within budget (total={bundle.total_after_discount})"
        assert float(bundle.total_after_discount) <= 100.0

    async def test_eval_bundle_with_discount(self, llm, product_repo, mocker):
        """'bundle + discount' — promo path must attach a code and discounted totals."""
        promo_service = mocker.MagicMock()
        promo_service.generate_code = mocker.AsyncMock(return_value="EVAL10")

        resp = await _agent(llm, product_repo, promo_service=promo_service).run(
            query="bundle a wireless mouse with a mechanical keyboard",
            store_id="store-eval",
            customer_id="cust-eval",
        )
        assert_latency(resp)
        assert resp.bundles, "expected a bundle"
        bundle = resp.bundles[0]
        assert bundle.total_discount > 0, "discount must be applied"
        assert float(bundle.total_discount) < float(bundle.total_original), "discount must reduce the total"
        assert resp.promo_code, "promo code should be attached when discounts are available"