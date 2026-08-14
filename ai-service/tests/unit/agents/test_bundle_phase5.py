"""Phase 5 bundle engine tests: budget-independent bundles, use-case intent, promo gating."""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.agents.bundle.agent import BundleSuggestionAgent
from app.application.recommendation.dto.recommendation_dto import BundleResponse
from app.application.recommendation.promo_service import PromoCodeService
from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money


def _product(pid: str, price: float, discount: float = 0.0) -> Product:
    return Product(
        id=pid,
        store_id="store_1",
        organization_id="o1",
        title=f"{pid.title()} product",
        product_type="keyboard" if "keyboard" in pid else "mouse",
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


@pytest.fixture
def product_repo():
    repo = AsyncMock()
    repo.find_many.return_value = [
        _product("mouse1", 25.0, 20.0),
        _product("keyboard1", 35.0, 10.0),
    ]
    return repo


@pytest.fixture
def llm():
    l = AsyncMock()
    l.structured_output.return_value.message.content = (
        '{"budget": null, "desired_items": ["mouse", "keyboard"], "use_case": null}'
    )
    return l


class TestBundleWithoutBudget:
    """Fix 5.2: budget=null must still produce bundles."""

    async def test_no_budget_returns_bundles(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I need a mouse and keyboard", store_id="store_1")
        assert isinstance(response, BundleResponse)
        assert len(response.bundles) > 0
        assert "Found" in (response.rationale or "")

    async def test_no_budget_bundles_at_normal_price(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I need a mouse and keyboard", store_id="store_1")
        assert response.budget == 0.0
        assert all(b.within_budget for b in response.bundles)
        assert all(b.total_discount == Decimal("0") for b in response.bundles)


class TestMultiProductIntent:
    """Fix 5.1: explicit multi-item requests produce multi-item bundles."""

    async def test_mouse_and_keyboard(self, product_repo, llm):
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I need a mouse and keyboard", store_id="store_1")
        two_item = [b for b in response.bundles if len(b.products) == 2]
        assert len(two_item) > 0

    async def test_use_case_setup_expands_to_categories(self, product_repo, llm):
        llm.structured_output.return_value.message.content = (
            '{"budget": null, "desired_items": [], "use_case": "gaming setup"}'
        )
        product_repo.find_many.return_value = [
            _product("keyboard1", 35.0, 10.0),
            _product("mouse1", 25.0, 20.0),
            _product("headset1", 40.0, 5.0),
        ]
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm)
        response = await agent.run(query="I want a gaming setup", store_id="store_1")
        assert len(response.bundles) > 0


class TestDiscountAndPromo:
    """Fix 5.3/5.4/5.5: discount only when needed; promo only with a real discount."""

    @pytest.fixture
    def promo_service(self):
        promo = AsyncMock(spec=PromoCodeService)
        promo.generate_code = AsyncMock(return_value="BUNDLE-REAL123")
        return promo

    async def test_bundle_fits_budget_no_promo(self, product_repo, llm, promo_service):
        llm.structured_output.return_value.message.content = (
            '{"budget": 200.0, "desired_items": ["mouse", "keyboard"], "use_case": null}'
        )
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="I need a mouse and keyboard with $200",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
        )
        assert len(response.bundles) > 0
        assert response.promo_code is None
        promo_service.generate_code.assert_not_awaited()

    async def test_discounted_bundle_gets_real_promo(self, product_repo, llm, promo_service):
        llm.structured_output.return_value.message.content = (
            '{"budget": 50.0, "desired_items": ["mouse", "keyboard"], "use_case": null}'
        )
        product_repo.find_many.return_value = [
            _product("mouse1", 30.0, 30.0),
            _product("keyboard1", 30.0, 20.0),
        ]
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="I need a mouse and keyboard with $50",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
        )
        assert len(response.bundles) > 0
        assert response.promo_code == "BUNDLE-REAL123"
        promo_service.generate_code.assert_awaited_once()

    async def test_platform_cannot_create_coupon_no_promo_shown(self, product_repo, llm, promo_service):
        promo_service.generate_code = AsyncMock(return_value=None)
        llm.structured_output.return_value.message.content = (
            '{"budget": 50.0, "desired_items": ["mouse", "keyboard"], "use_case": null}'
        )
        product_repo.find_many.return_value = [
            _product("mouse1", 30.0, 30.0),
            _product("keyboard1", 30.0, 20.0),
        ]
        agent = BundleSuggestionAgent(product_repo=product_repo, llm=llm, promo_service=promo_service)
        response = await agent.run(
            query="I need a mouse and keyboard with $50",
            store_id="store_1",
            store_capabilities={"has_promo_codes": True},
        )
        assert response.promo_code is None
