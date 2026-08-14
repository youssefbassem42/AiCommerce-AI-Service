from decimal import Decimal

from app.agents.bundle.tools import (
    expand_use_case,
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
        budget, items, use_case = await parse_budget("I have $300 and want a monitor", llm=mock_provider)
        assert budget == 300.0
        assert items == ["monitor"]
        assert use_case == "office work"

    async def test_parse_budget_no_budget(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": ["monitor", "keyboard"], "use_case": null}'
        )
        budget, items, use_case = await parse_budget("I want a monitor and keyboard", llm=mock_provider)
        assert budget is None
        assert items == ["monitor", "keyboard"]
        assert use_case is None

    async def test_parse_budget_multiple_items(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": 500.0, "desired_items": ["monitor", "keyboard", "mouse"], "use_case": "gaming"}'
        )
        budget, items, use_case = await parse_budget(
            "$500 for a monitor, keyboard, and mouse for gaming", llm=mock_provider
        )
        assert budget == 500.0
        assert len(items) == 3
        assert use_case == "gaming"

    async def test_parse_budget_use_case_only(self, mock_provider):
        mock_provider.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": [], "use_case": "gaming setup"}'
        )
        budget, items, use_case = await parse_budget("I want a gaming setup", llm=mock_provider)
        assert budget is None
        assert items == []
        assert use_case == "gaming setup"


class TestExpandUseCase:
    def test_unknown_use_case_returns_empty(self):
        assert expand_use_case(None) == []
        assert expand_use_case("something weird") == []

    def test_gaming_setup_expands(self):
        categories = expand_use_case("gaming setup")
        assert "keyboard" in categories
        assert "mouse" in categories
        assert "headset" in categories

    def test_home_office_setup_expands(self):
        categories = expand_use_case("home office setup")
        assert "monitor" in categories
        assert "keyboard" in categories
        assert "mouse" in categories

    def test_case_insensitive(self):
        categories = expand_use_case("GAMING Setup")
        assert "keyboard" in categories


class TestKnapsackBundles:
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

    def test_no_budget_still_finds_bundles(self):
        """Fix 5.2: budget=None must not gate bundle generation."""
        products = [self._make_product("p1", 100.0), self._make_product("p2", 150.0)]
        result = knapsack_bundles({"monitor": products, "keyboard": products}, None)
        assert len(result) > 0
        assert any(len(b) == 2 for b in result)

    def test_no_budget_includes_expensive_products(self):
        products = [self._make_product("p1", 500.0), self._make_product("p2", 800.0)]
        result = knapsack_bundles({"monitor": products}, None)
        assert any(len(b) == 1 for b in result)
        assert any(b[0].id == "p1" for b in result)
        assert any(b[0].id == "p2" for b in result)

    def test_discounted_combination_generated(self):
        """Fix 5.4: a pair whose NORMAL total exceeds the budget but whose
        discounted total fits must still be generated."""
        products = [self._make_product("p1", 30.0, 30.0), self._make_product("p2", 30.0, 20.0)]
        result = knapsack_bundles({"mouse": products, "keyboard": products}, 50.0)
        pairs = [b for b in result if len(b) == 2]
        assert len(pairs) >= 1

    def test_discounted_only_product_eligible(self):
        """Fix 5.4: a product that only fits after its max discount is eligible."""
        products = [self._make_product("p1", 60.0, 30.0), self._make_product("p2", 30.0)]
        result = knapsack_bundles({"mouse": products}, 50.0)
        assert any(len(b) == 1 and b[0].id == "p1" for b in result)


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

    def test_bundle_within_budget_is_normal_price(self):
        """Fix 5.3: total <= budget -> normal price, no discount applied."""
        product = self._make_product("p1", 200.0, 10.0)
        bundles = [[product]]
        scored = score_bundles(bundles, 300.0, {"monitor": [product]})
        assert len(scored) == 1
        best = scored[0]
        assert best.total_original == Decimal("200")
        assert best.total_discount == Decimal("0")
        assert best.total_after_discount == Decimal("200")
        assert best.within_budget is True
        assert best.products[0].discount_pct == 0.0

    def test_bundle_needs_discount_to_fit_budget(self):
        """Fix 5.4: total > budget -> max allowed discount; discounted total must fit."""
        product = self._make_product("p1", 200.0, 20.0)
        bundles = [[product]]
        scored = score_bundles(bundles, 160.0, {"monitor": [product]})
        assert len(scored) == 1
        best = scored[0]
        assert best.total_original == Decimal("200")
        assert best.total_discount == Decimal("40")
        assert best.total_after_discount == Decimal("160")
        assert best.within_budget is True

    def test_bundle_not_within_budget_even_with_max_discount(self):
        product = self._make_product("p1", 200.0, 10.0)
        bundles = [[product]]
        scored = score_bundles(bundles, 150.0, {"monitor": [product]})
        assert len(scored) == 1
        best = scored[0]
        assert best.total_after_discount == Decimal("180")
        assert best.within_budget is False

    def test_no_budget_normal_price_and_within_budget(self):
        """Fix 5.2: budget=None -> bundles are always within budget at normal price."""
        product = self._make_product("p1", 200.0, 10.0)
        bundles = [[product]]
        scored = score_bundles(bundles, None, {"monitor": [product]})
        assert len(scored) == 1
        best = scored[0]
        assert best.total_discount == Decimal("0")
        assert best.total_after_discount == Decimal("200")
        assert best.within_budget is True

    def test_within_budget_bundles_sort_first(self):
        p1 = self._make_product("p1", 200.0, 10.0)
        p2 = self._make_product("p2", 500.0, 5.0)
        bundles = [[p2], [p1]]
        scored = score_bundles(bundles, 180.0, {"monitor": [p1, p2]})
        assert scored[0].within_budget is True
        assert scored[-1].within_budget is False
