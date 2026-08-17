"""Phase 5 (Domain 5) before/after evidence: B16 complementarity, B17 bundle/promo
consistency, L4 promotion lifecycle.

Every test here encodes a production defect diagnosed in Domain 5 and must FAIL
against the pre-fix implementation (they are the before-evidence), then pass
after the fixes.
"""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.bundle.agent import BundleSuggestionAgent
from app.agents.bundle.tools import promo_capable
from app.application.contracts.bundle import bundle_payload_from_candidates
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    DiscountInfo,
)
from app.application.recommendation.promo_service import PromoCodeService, PromoValidationResult
from app.application.recommendation.services import BundleSuggestionService
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money

CATEGORY_NAMES = {
    "1": "Electronics",
    "2": "Fashion",
    "5": "Accessories",
    "7": "Kitchenware",
    "9": "Office",
}


def _product(
    pid: str,
    title: str,
    price: float,
    category_id: str,
    product_type: str | None = None,
    stock: int = 5,
    discount: float = 0.0,
    status: str = "active",
) -> Product:
    return Product(
        id=pid,
        store_id="store_1",
        organization_id="o1",
        title=title,
        product_type=product_type,
        category_id=category_id,
        status=status,
        variants=[
            Variant(
                id=f"v-{pid}",
                sku=f"SKU-{pid}",
                title=f"V-{pid}",
                price=Money(amount=Decimal(str(price))),
                inventory_quantity=stock,
            )
        ],
        metadata={"max_discount_pct": discount},
    )


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = '{"budget": null, "desired_items": [], "use_case": null}'
    return l


@pytest.fixture
def promo_service():
    promo = AsyncMock(spec=PromoCodeService)
    promo.generate_code = AsyncMock(return_value="BUNDLE-REAL123")
    promo.validate_code = AsyncMock(
        return_value=PromoValidationResult(status="valid", discount_amount=Decimal("20"), reason=None)
    )
    return promo


@pytest.fixture
def capabilities_repo():
    repo = AsyncMock()
    repo.get_or_detect.return_value = MagicMock(capabilities={"has_promo_codes": False})
    return repo


@pytest.fixture
def recommendation_repo():
    return AsyncMock()


class TestComplementaryBundles:
    """B16: bundles must be commercially meaningful, not arbitrary combinations."""

    def _laptop_catalog(self):
        return [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("l2", "Budget Laptop", 1700.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
            _product("b1", "Laptop Backpack", 80.0, "5", product_type="bag"),
        ]

    async def test_explicit_laptop_bundle_is_complementary(self, llm):
        """'laptop with a mouse and a bag' must yield Laptop + Mouse + Bag, not
        Laptop + Laptop or a lone laptop."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse", "bag"], "use_case": null}'
        )
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(self._laptop_catalog())
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="I need a laptop with a mouse and a bag under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        assert len(response.bundles) > 0
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Gaming Laptop RTX" in titles
        assert "Wireless Mouse" in titles
        assert "Laptop Backpack" in titles
        assert best.within_budget is True
        assert float(best.total_after_discount) <= 2000.0

    async def test_camera_bundle_is_complementary(self, llm):
        """'camera, memory card and tripod' must yield the complementary trio."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 900.0, "desired_items": ["camera", "memory card", "tripod"], "use_case": null}'
        )
        catalog = [
            _product("c1", "Mirrorless Camera", 700.0, "1", product_type="camera"),
            _product("s1", "SD Memory Card 128GB", 40.0, "5", product_type="memory card"),
            _product("t1", "Camera Tripod", 90.0, "5", product_type="tripod"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="I need a camera with a memory card and tripod under $900",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        assert len(response.bundles) > 0
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Mirrorless Camera" in titles
        assert "SD Memory Card 128GB" in titles
        assert "Camera Tripod" in titles

    async def test_complementarity_outranks_same_category(self, llm):
        """Laptop + Mouse must rank above Laptop + Laptop (same category)."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2500.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("l2", "Budget Laptop", 800.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a mouse under $2500",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Wireless Mouse" in titles
        assert len(best.products) == 2
        mouse_bundles = [b for b in response.bundles if "Wireless Mouse" in {p.product_title for p in b.products}]
        assert mouse_bundles, "the complementary bundle must be in the ranked output"
        # A same-category pair (Laptop + Laptop) must never outrank the
        # complementary bundle, no matter its discount.
        for b in response.bundles:
            if "Wireless Mouse" not in {p.product_title for p in b.products}:
                assert b.rank > mouse_bundles[0].rank

    async def test_same_category_allowed_when_requested_twice(self, llm):
        """'two controllers for the console' must allow Console + Controller + Controller."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["console", "controller", "controller"], "use_case": null}'
        )
        catalog = [
            _product("cs1", "Gaming Console", 250.0, "1", product_type="console"),
            _product("ct1", "Wireless Controller", 60.0, "5", product_type="controller"),
            _product("ct2", "Wired Controller", 40.0, "5", product_type="controller"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="two controllers for this console, under $400",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        best = response.bundles[0]
        types = [p.product_title for p in best.products]
        assert "Gaming Console" in types
        assert sum("Controller" in t for t in types) == 2

    async def test_out_of_stock_products_excluded(self, llm):
        """Laptop + Mouse must never be selected when the mouse is out of stock."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse", "bag"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse", stock=0),
            _product("b1", "Laptop Backpack", 80.0, "5", product_type="bag"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a mouse and a bag under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Wireless Mouse" not in titles
        assert "Gaming Laptop RTX" in titles

    async def test_inactive_products_excluded(self, llm):
        """Archived products must never become bundle items."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "bag"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("b1", "Laptop Backpack", 80.0, "5", product_type="bag"),
            _product("b2", "Retired Laptop Bag", 70.0, "5", product_type="bag", status="archived"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a bag under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        titles = {p.product_title for b in response.bundles for p in b.products}
        assert "Retired Laptop Bag" not in titles

    async def test_budget_is_a_hard_constraint(self, llm):
        """final_total must never exceed the budget."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse", "bag"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Premium Laptop", 1900.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 200.0, "5", product_type="mouse"),
            _product("b1", "Laptop Backpack", 100.0, "5", product_type="bag"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with mouse and bag under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        assert all(b.within_budget for b in response.bundles)
        for b in response.bundles:
            assert float(b.total_after_discount) <= 2000.0

    async def test_no_bundle_within_budget_is_honest(self, llm):
        """Over-budget bundles must not be presented as valid selections."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 500.0, "desired_items": ["laptop", "bag"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Premium Laptop", 1900.0, "1", product_type="laptop"),
            _product("b1", "Laptop Backpack", 100.0, "5", product_type="bag"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a bag under $500",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        assert all(b.within_budget for b in response.bundles)


class TestRankingAndPersistence:
    """B17: one authoritative selected bundle end to end."""

    def _catalog(self):
        # Bundle A: high complementarity (laptop+mouse), normal price within budget.
        # Bundle B: low complementarity (laptop+laptop), large discount.
        return [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("l2", "Budget Laptop", 1700.0, "1", product_type="laptop", discount=25.0),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]

    async def test_rank_is_assigned_and_selected_is_rank_one(self, llm):
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(self._catalog())
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a mouse under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        assert len(response.bundles) > 0
        ranks = [b.rank for b in response.bundles]
        assert sorted(ranks) == ranks
        assert response.bundles[0].rank == 1
        assert "Wireless Mouse" in {p.product_title for p in response.bundles[0].products}

    async def test_complementarity_beats_discount(self, llm):
        """A complementary bundle must outrank a same-category bundle with a big discount."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(self._catalog())
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="laptop with a mouse under $2000",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Wireless Mouse" in titles

    async def test_persistence_saves_the_selected_bundle(self, llm, capabilities_repo, recommendation_repo):
        """Mongo persistence must store the rank-1 bundle exactly as returned."""
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(self._catalog())
        service = BundleSuggestionService(
            product_repo=repo,
            llm=llm,
            capabilities_repo=capabilities_repo,
            recommendation_repo=recommendation_repo,
        )
        llm.structured_output.return_value.message.content = (
            '{"budget": 2000.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        response = await service.suggest(
            query="laptop with a mouse under $2000",
            store_id="store_1",
            customer_id="cust_1",
            context={"conversation": {"conversation_id": "conv-1"}},
        )
        assert len(response.bundles) > 0
        top = response.bundles[0]
        assert top.rank == 1
        recommendation_repo.save_bundle_suggestion.assert_awaited_once()
        saved = recommendation_repo.save_bundle_suggestion.await_args.args[0]
        expected_ids = [p.product_id for p in top.products]
        assert saved.product_ids == expected_ids
        assert saved.rank == 1
        assert saved.total_price == float(top.total_after_discount)

    async def test_promo_targets_the_selected_bundle_only(self, llm, promo_service):
        """generate_code must be called with exactly the selected bundle's products."""
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", product_type="laptop", discount=10.0),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
            _product("b1", "Laptop Backpack", 80.0, "5", product_type="bag"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="laptop with a mouse and a bag under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        promo_service.generate_code.assert_awaited_once()
        _, kwargs = promo_service.generate_code.await_args
        selected_ids = {p.product_id for p in response.bundles[0].products}
        assert set(kwargs["product_ids"]) == selected_ids


class TestPromoCapabilityConsistency:
    """B17: one source of truth for has_promo_codes."""

    def test_capability_default_is_false_everywhere(self):
        assert promo_capable({}) is False
        assert promo_capable(None) is False
        assert promo_capable({"has_promo_codes": False}) is False
        assert promo_capable({"has_promo_codes": True}) is True

    async def test_no_capability_means_no_promo_api_call(self, llm, promo_service):
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", discount=10.0, product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            category_names=CATEGORY_NAMES,
        )
        promo_service.generate_code.assert_not_awaited()
        assert response.promo_code is None
        assert response.promo_status is None

    async def test_capability_true_routes_to_promo(self, llm, promo_service):
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", discount=10.0, product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo_service)
        await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        promo_service.generate_code.assert_awaited_once()


class TestPromotionLifecycle:
    """L4: create -> validate -> persist -> return, never a fabricated success."""

    async def test_created_promo_is_validated_against_real_bundle(self, llm, promo_service):
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", discount=10.0, product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        assert response.promo_code == "BUNDLE-REAL123"
        assert response.promo_status == "validated"
        promo_service.validate_code.assert_awaited_once()
        _, kwargs = promo_service.validate_code.await_args
        assert kwargs["store_id"] == "store_1"
        assert kwargs["code"] == "BUNDLE-REAL123"
        assert Decimal(kwargs["subtotal"]) == response.bundles[0].total_original

    async def test_invalid_promo_is_dropped(self, llm):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value="BUNDLE-BAD")
        promo.validate_code = AsyncMock(return_value=PromoValidationResult(status="invalid", reason="expired"))
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", discount=10.0, product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo)
        response = await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        assert response.promo_code is None
        assert response.promo_status == "invalid"
        assert "promo code" not in (response.rationale or "").lower()

    async def test_unverifiable_promo_is_not_claimed_verified(self, llm):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value="BUNDLE-UNK")
        promo.validate_code = AsyncMock(
            return_value=PromoValidationResult(status="unavailable", reason="validation endpoint down")
        )
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 330.0, "1", discount=10.0, product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo)
        response = await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        assert response.promo_code == "BUNDLE-UNK"
        assert response.promo_status == "unverified"
        assert "confirmed" not in (response.rationale or "").lower()

    async def test_creation_failure_yields_no_promo_and_no_validation(self, llm):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value=None)
        llm.structured_output.return_value.message.content = (
            '{"budget": 400.0, "desired_items": ["laptop", "mouse"], "use_case": null}'
        )
        catalog = [
            _product("l1", "Gaming Laptop RTX", 300.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo)
        response = await agent.run(
            query="laptop with a mouse under $400",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            category_names=CATEGORY_NAMES,
        )
        assert response.promo_code is None
        promo.validate_code.assert_not_awaited()


class TestShoppingStateIntegration:
    """Domain 4 context must flow into the bundle engine (multi-turn)."""

    async def test_shopping_state_seeds_primary_and_budget(self, llm, promo_service):
        """'Add the accessories' must continue the laptop shopping state."""
        llm.structured_output.return_value.message.content = '{"budget": null, "desired_items": [], "use_case": null}'
        catalog = [
            _product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop"),
            _product("m1", "Wireless Mouse", 100.0, "5", product_type="mouse"),
            _product("b1", "Laptop Backpack", 80.0, "5", product_type="bag"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="Add the accessories",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
            shopping_state={"category": "laptop", "budget": 2500.0, "use_case": "gaming"},
            category_names=CATEGORY_NAMES,
        )
        assert len(response.bundles) > 0
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Gaming Laptop RTX" in titles
        assert float(best.total_after_discount) <= 2500.0

    async def test_current_message_overrides_stale_state(self, llm):
        """'Actually, make it a camera' must replace the laptop primary."""
        llm.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": ["camera", "tripod"], "use_case": null}'
        )
        catalog = [
            _product("c1", "Mirrorless Camera", 700.0, "1", product_type="camera"),
            _product("t1", "Camera Tripod", 90.0, "5", product_type="tripod"),
        ]
        repo = AsyncMock()
        repo.find_many.side_effect = _find_many_for(catalog)
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(
            query="Actually, make it a camera bundle with a tripod",
            store_id="store_1",
            shopping_state={"category": "laptop", "budget": 2500.0, "use_case": "gaming"},
            category_names=CATEGORY_NAMES,
        )
        best = response.bundles[0]
        titles = {p.product_title for p in best.products}
        assert "Mirrorless Camera" in titles
        assert all("Laptop" not in t for t in titles)


class TestTenantIsolation:
    async def test_candidates_are_store_scoped(self, llm):
        """Bundle discovery must only ever query the requesting store."""
        llm.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": ["laptop"], "use_case": null}'
        )
        repo = AsyncMock()
        repo.find_many.return_value = [_product("l1", "Gaming Laptop RTX", 1500.0, "1", product_type="laptop")]
        agent = BundleSuggestionAgent(product_repo=repo, llm=llm)
        response = await agent.run(query="laptop bundle", store_id="store_A", category_names=CATEGORY_NAMES)
        assert response.store_id == "store_A"
        for call in repo.find_many.await_args_list:
            assert call.kwargs or call.args[0].get("store_id") == "store_A"


class TestResponseContract:
    async def test_bundle_payload_keeps_fields_and_status(self):
        candidate = BundleCandidate(
            products=[
                DiscountInfo(
                    product_id="l1",
                    product_title="Gaming Laptop RTX",
                    original_price=Decimal("1500"),
                    discount_pct=10.0,
                    price_after_discount=Decimal("1350"),
                    product_url="https://x/l1",
                    image_url="https://x/l1.jpg",
                )
            ],
            total_original=Decimal("1500"),
            total_discount=Decimal("150"),
            total_after_discount=Decimal("1350"),
            remaining_budget=0.0,
            within_budget=True,
            promo_code="BUNDLE-X",
            promo_status="validated",
            rank=1,
        )
        payload = bundle_payload_from_candidates([candidate])
        assert payload is not None
        assert payload.items[0].product_id == "l1"
        assert payload.total_original == "1500"
        assert payload.total_discount == "150"
        assert payload.promo_code == "BUNDLE-X"
        assert payload.promo_status == "validated"


class TestPromoCodeServiceValidation:
    """L4: PromoCodeService.validate_code — deterministic, honest normalization."""

    def _connection(self, endpoints=None, schemas=None, raw_spec=None):
        from app.domain.integration.entities.integration_connection import (
            ConnectionStatus,
            IntegrationConnection,
        )
        from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType
        from app.domain.integration.value_objects.entity_mapping import EntityMapping

        return IntegrationConnection(
            id="conn_1",
            store_id="s1",
            organization_id="o1",
            name="Shop API",
            platform_name="Shop",
            status=ConnectionStatus.ACTIVE,
            raw_spec=raw_spec
            or {
                "servers": [{"url": "https://api.shop.test"}],
                "paths": {
                    "/api/Checkout/validate-promo": {
                        "post": {
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/ValidatePromoDto",
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "components": {
                    "schemas": {
                        "ValidatePromoDto": {
                            "type": "object",
                            "properties": {"promoCode": {"type": "string"}, "subtotal": {"type": "number"}},
                        }
                    }
                },
            },
            auth_config=AuthConfig(type=AuthType.BEARER, credentials_location="header", name="token", scheme="bearer"),
            encrypted_credentials="encrypted-blob",
            entity_mappings=[EntityMapping(entity_type="discount", id_field="id", list_path="/coupons")],
            discovered_endpoints=endpoints
            or [
                {"path": "/api/Checkout/validate-promo", "method": "POST", "summary": "Validate a promo code"},
            ],
            discovered_schemas=schemas
            or {
                "POST /api/Checkout/validate-promo": {
                    "fields": [{"name": "promoCode", "type": "string"}, {"name": "subtotal", "type": "number"}]
                }
            },
        )

    @pytest.fixture
    def enable_promo_codes(self, monkeypatch):
        monkeypatch.setattr("app.application.recommendation.promo_service.ai_settings.PROMO_CODES_ENABLED", True)

    @pytest.fixture
    def disable_promo_codes(self, monkeypatch):
        monkeypatch.setattr("app.application.recommendation.promo_service.ai_settings.PROMO_CODES_ENABLED", False)

    async def _service(self, connection, post_result=None, post_side_effect=None):
        from app.infrastructure.http.clients.base_client import ExternalApiClient
        from app.infrastructure.mongodb.repositories.integration_connection_repository import (
            IntegrationConnectionMongoRepository,
        )

        connection_repo = AsyncMock(spec=IntegrationConnectionMongoRepository)
        connection_repo.find_many.return_value = [connection]
        service = PromoCodeService(connection_repo=connection_repo)
        client = AsyncMock(spec=ExternalApiClient)
        client.post.return_value = post_result
        if post_side_effect is not None:
            client.post.side_effect = post_side_effect
        service._build_client = MagicMock(return_value=client)
        return service, client

    async def test_validate_positive(self, enable_promo_codes):
        service, client = await self._service(self._connection(), post_result={"isValid": True, "discountAmount": 12.5})
        result = await service.validate_code(store_id="s1", code="BUNDLE-ABC", subtotal=Decimal("300.00"))
        assert result.status == "valid"
        assert result.discount_amount == Decimal("12.5")
        client.post.assert_awaited_once()
        _, kwargs = client.post.await_args
        assert kwargs["body"] == {"promoCode": "BUNDLE-ABC", "subtotal": 300.0}

    async def test_validate_negative(self, enable_promo_codes):
        service, _ = await self._service(self._connection(), post_result={"isValid": False, "message": "expired"})
        result = await service.validate_code(store_id="s1", code="BUNDLE-EXPIRED", subtotal=Decimal("300.00"))
        assert result.status == "invalid"
        assert result.reason == "expired"

    async def test_validate_unknown_response_never_claims_verified(self, enable_promo_codes):
        service, _ = await self._service(self._connection(), post_result={"message": "processed"})
        result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
        assert result.status == "unavailable"

    async def test_validate_http_failure_is_unavailable(self, enable_promo_codes):
        service, _ = await self._service(self._connection(), post_side_effect=Exception("502 Bad Gateway"))
        result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
        assert result.status == "unavailable"

    async def test_validate_no_connection_is_unavailable(self, enable_promo_codes):
        from app.infrastructure.mongodb.repositories.integration_connection_repository import (
            IntegrationConnectionMongoRepository,
        )

        connection_repo = AsyncMock(spec=IntegrationConnectionMongoRepository)
        connection_repo.find_many.return_value = []
        service = PromoCodeService(connection_repo=connection_repo)
        result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
        assert result.status == "unavailable"

    async def test_validate_connection_mapping_case_insensitive(self, enable_promo_codes):
        """Live .NET spec maps the entity as 'Discount'; the coupon check must be
        case-insensitive or the checkout connection is never found."""
        from app.domain.integration.value_objects.entity_mapping import EntityMapping

        connection = self._connection()
        connection.entity_mappings = [EntityMapping(entity_type="Discount", id_field="id", list_path="/coupons")]
        service, client = await self._service(connection, post_result={"isValid": True, "discountAmount": 5})
        result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
        assert result.status == "valid"
        client.post.assert_awaited_once()
        _, kwargs = client.post.await_args
        assert kwargs["body"]["promoCode"] == "BUNDLE-X"

    async def test_validate_disabled_config_is_unavailable(self, disable_promo_codes):
        service, client = await self._service(self._connection(), post_result={"isValid": True})
        result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
        assert result.status == "unavailable"
        client.post.assert_not_awaited()

    async def test_validate_accepts_common_success_shapes(self, enable_promo_codes):
        for body in (
            {"valid": True},
            {"success": True},
            {"is_valid": True},
            {"isValidPromo": True, "discountAmount": 5},
            {"valid": "true"},
        ):
            service, _ = await self._service(self._connection(), post_result=body)
            result = await service.validate_code(store_id="s1", code="BUNDLE-X", subtotal=Decimal("300.00"))
            assert result.status == "valid", f"shape {body} must normalize to valid"

    async def test_coupon_payload_satisfies_platform_contract(self, enable_promo_codes):
        """CreateCouponDto requires code + discountPercentage + expiryDate — the payload
        must carry all three when the platform schema declares them."""
        from datetime import datetime

        raw = {
            "servers": [{"url": "https://api.shop.test"}],
            "paths": {
                "/api/admin/coupons": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/CreateCouponDto"}}
                            }
                        }
                    }
                }
            },
            "components": {
                "schemas": {
                    "CreateCouponDto": {
                        "type": "object",
                        "required": ["code", "discountPercentage", "expiryDate"],
                        "properties": {
                            "code": {"type": "string"},
                            "discountPercentage": {"type": "number"},
                            "expiryDate": {"type": "string", "format": "date-time"},
                        },
                    }
                }
            },
        }
        connection = self._connection(
            endpoints=[{"path": "/api/admin/coupons", "method": "POST", "summary": "Create coupon"}],
            schemas={
                "POST /api/admin/coupons": {
                    "fields": [
                        {"name": "code", "type": "string"},
                        {"name": "discountPercentage", "type": "number"},
                        {"name": "expiryDate", "type": "string"},
                    ]
                }
            },
            raw_spec=raw,
        )
        service, client = await self._service(connection, post_result=None)
        # The platform echoes the coupon it created (the payload code). A real
        # integration would return the code it stored; the mock must echo the
        # request body because the payload necessarily precedes the response.
        client.post.side_effect = lambda *args, **kwargs: {"code": kwargs["body"]["code"]}
        code = await service.generate_code(store_id="s1", product_ids=["p1"], discount_pct=10.0)
        assert code and code.startswith("BUNDLE-")
        client.post.assert_awaited_once()
        body = client.post.await_args.kwargs["body"]
        assert body["code"] == code
        assert body["discountPercentage"] == 10.0
        assert "expiryDate" in body
        expiry = datetime.fromisoformat(body["expiryDate"].replace("Z", "+00:00"))
        assert expiry.tzinfo is not None
        assert expiry > datetime.now(UTC)


def _find_many_for(catalog):
    def factory(filters, *args, **kwargs):
        store = filters.get("store_id")
        matched = [p for p in catalog if p.store_id == store]
        if "product_type" in filters and filters.get("product_type"):
            regex = filters["product_type"].get("$regex", "").lower()
            type_matched = [p for p in matched if regex in (p.product_type or "").lower()]
            if type_matched:
                return type_matched
        if "title" in filters and filters.get("title"):
            regex = filters["title"].get("$regex", "").lower()
            title_matched = [p for p in matched if regex in (p.title or "").lower()]
            if title_matched:
                return title_matched
        return matched

    return factory
