from decimal import Decimal

from app.agents.bundle.tools import (
    knapsack_bundles,
    parse_budget,
    score_bundles,
)
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
)
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money


class TestParseBudget:
    async def test_parse_budget_with_budget(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": 300.0, "desired_items": ["monitor"], "use_case": "office work"}'
        )
        budget, items = await parse_budget("I have $300 and want a monitor", llm=mock_provider)
        assert budget == 300.0
        assert items == ["monitor"]

    async def test_parse_budget_no_budget(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": ["monitor", "keyboard"], "use_case": null}'
        )
        budget, items = await parse_budget("I want a monitor and keyboard", llm=mock_provider)
        assert budget is None
        assert items == ["monitor", "keyboard"]

    async def test_parse_budget_multiple_items(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": 500.0, "desired_items": ["monitor", "keyboard", "mouse"], "use_case": "gaming"}'
        )
        budget, items = await parse_budget("$500 for a monitor, keyboard, and mouse for gaming", llm=mock_provider)
        assert budget == 500.0
        assert len(items) == 3


class TestKnapsackBundles:
    def _make_product(self, pid: str, price: float) -> Product:
        return Product(
            id=pid,
            store_id="s1",
            organization_id="o1",
            title=f"Product {pid}",
            variants=[
                Variant(
                    id=f"v-{pid}",
                    sku=f"SKU-{pid}",
                    title=f"V-{pid}",
                    price=Money(amount=Decimal(str(price))),
                    inventory_quantity=5,
                )
            ],
        )

    def test_single_item_bundles(self):
        products = [self._make_product("p1", 100.0), self._make_product("p2", 150.0)]
        result = knapsack_bundles({"monitor": products}, 250.0)
        assert len(result) > 0
        assert any(len(b) == 1 for b in result)
        assert any(len(b) == 2 for b in result)

    def test_no_affordable_products(self):
        products = [self._make_product("p1", 500.0)]
        result = knapsack_bundles({"monitor": products}, 100.0)
        assert result == []

    def test_budget_exact_match(self):
        p1 = self._make_product("p1", 100.0)
        p2 = self._make_product("p2", 200.0)
        result = knapsack_bundles({"monitor": [p1, p2]}, 300.0)
        two_item = [b for b in result if len(b) == 2]
        assert len(two_item) >= 1

    def test_three_item_bundle(self):
        products = [
            self._make_product("p1", 50.0),
            self._make_product("p2", 75.0),
            self._make_product("p3", 100.0),
            self._make_product("p4", 200.0),
        ]
        result = knapsack_bundles({"monitor": products}, 225.0)
        three_item = [b for b in result if len(b) == 3]
        assert len(three_item) >= 1


class TestScoreBundles:
    def _make_product(self, pid: str, price: float, discount: float = 0.0) -> Product:
        return Product(
            id=pid,
            store_id="s1",
            organization_id="o1",
            title=f"Product {pid}",
            variants=[
                Variant(
                    id=f"v-{pid}",
                    sku=f"SKU-{pid}",
                    title=f"V-{pid}",
                    price=Money(amount=Decimal(str(price))),
                    inventory_quantity=5,
                )
            ],
            metadata={"max_discount_pct": discount},
        )

    def test_score_bundles_returns_candidates(self):
        p1 = self._make_product("p1", 100.0, 10.0)
        p2 = self._make_product("p2", 150.0, 5.0)
        bundles = [[p1], [p2], [p1, p2]]
        scored = score_bundles(bundles, 300.0, {"monitor": [p1, p2]})
        assert len(scored) > 0
        assert all(isinstance(b, BundleCandidate) for b in scored)

    def test_score_applies_discounts(self):
        product = self._make_product("p1", 200.0, 10.0)
        bundles = [[product]]
        scored = score_bundles(bundles, 300.0, {"monitor": [product]})
        assert len(scored) == 1
        best = scored[0]
        assert best.total_original == Decimal("200")
        assert best.total_discount == Decimal("20")
        assert best.total_after_discount == Decimal("180")
