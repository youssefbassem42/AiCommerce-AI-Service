from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC
import pytest

from app.application.commerce.services import ProductService, OrderService, InventoryService
from app.domain.commerce.aggregates.product import Product, Variant, ProductOption
from app.domain.commerce.aggregates.order import Order, LineItem
from app.domain.commerce.value_objects.money import Money
from app.domain.commerce.value_objects.audit import AuditInfo


@pytest.fixture
def product_repo():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_store = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def product_service(product_repo):
    return ProductService(repository=product_repo)


@pytest.fixture
def order_repo():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_store = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def order_service(order_repo):
    return OrderService(repository=order_repo)


class TestCommerceServiceBugs:

    async def test_product_update_preserves_variant_ids(self, product_service, product_repo):
        original_variant_id = "variant-001"
        original_option_id = "option-001"
        entity = Product(
            id="prod-1",
            store_id="s1",
            organization_id="o1",
            title="Test Product",
            variants=[
                Variant(id=original_variant_id, sku="SKU001", title="V1",
                        price=Money(amount="10.00", currency="USD")),
            ],
            options=[
                ProductOption(id=original_option_id, name="Size", values=["S", "M"]),
            ],
            audit=AuditInfo(created_by="test"),
        )
        product_repo.find_by_id.return_value = entity
        product_repo.update.side_effect = lambda e: e

        from app.application.commerce.dto import ProductUpdateDTO
        update_data = ProductUpdateDTO(
            title="Updated",
            variants=[{"id": original_variant_id, "sku": "SKU002", "title": "V2",
                       "price": {"amount": "15.00", "currency": "USD"}}],
            options=[{"id": original_option_id, "name": "Color", "values": ["Red", "Blue"]}],
        )

        await product_service.update("prod-1", update_data)
        updated_entity = product_repo.update.call_args[0][0]

        assert updated_entity.variants[0].id == original_variant_id, (
            "Variant IDs should be preserved when variant has matching id"
        )
        assert updated_entity.options[0].id == original_option_id, (
            "Option IDs should be preserved when option has matching id"
        )

    async def test_product_update_preserves_variant_ids_when_not_updated(self, product_service, product_repo):
        original_variant_id = "variant-001"
        entity = Product(
            id="prod-1",
            store_id="s1",
            organization_id="o1",
            title="Test Product",
            variants=[
                Variant(id=original_variant_id, sku="SKU001", title="V1",
                        price=Money(amount="10.00", currency="USD")),
            ],
            audit=AuditInfo(created_by="test"),
        )
        product_repo.find_by_id.return_value = entity
        product_repo.update.side_effect = lambda e: e

        from app.application.commerce.dto import ProductUpdateDTO
        update_data = ProductUpdateDTO(title="Just Title Update")

        await product_service.update("prod-1", update_data)

        updated_entity = product_repo.update.call_args[0][0]
        variant_ids = [v.id for v in updated_entity.variants]
        assert original_variant_id in variant_ids, (
            "Original variant IDs preserved when variants not in update payload"
        )

    async def test_product_update_assigns_new_id_for_new_variants(self, product_service, product_repo):
        entity = Product(
            id="prod-1",
            store_id="s1",
            organization_id="o1",
            title="Test Product",
            variants=[],
            options=[],
            audit=AuditInfo(created_by="test"),
        )
        product_repo.find_by_id.return_value = entity
        product_repo.update.side_effect = lambda e: e

        from app.application.commerce.dto import ProductUpdateDTO
        update_data = ProductUpdateDTO(
            variants=[{"sku": "NEW001", "title": "New V",
                       "price": {"amount": "20.00", "currency": "USD"}}],
        )

        await product_service.update("prod-1", update_data)

        updated_entity = product_repo.update.call_args[0][0]
        assert updated_entity.variants[0].id is not None
        assert len(updated_entity.variants[0].id) > 0

    async def test_order_to_dto_includes_line_items(self, order_service, order_repo):
        audit = AuditInfo(created_by="test")
        now = datetime.now(UTC)
        entity = Order(
            id="ord-1",
            store_id="s1",
            org_id="o1",
            customer_id="c1",
            customer_email="c@example.com",
            line_items=[
                LineItem(
                    id="li-1", variant_id="v1", product_id="p1",
                    title="Item 1", quantity=2,
                    price=Money(amount="10.00", currency="USD"),
                ),
                LineItem(
                    id="li-2", variant_id="v2", product_id="p2",
                    title="Item 2", quantity=1,
                    price=Money(amount="25.00", currency="USD"),
                ),
            ],
            financial_status="paid",
            fulfillment_status="fulfilled",
            currency="USD",
            tags=[],
            audit=audit,
            created_at=now,
            updated_at=now,
        )
        order_repo.find_by_id.return_value = entity
        result = await order_service.get_by_id("ord-1")
        assert len(result.line_items) > 0, (
            f"Order DTO should contain line items, got {len(result.line_items)}. "
            f"Entity has {len(entity.line_items)} line items."
        )

    async def test_inventory_bulk_update_returns_updated_count(self):
        repo = AsyncMock()
        repo.find_many = AsyncMock(return_value=[
            MagicMock(product_id="p1", audit=AuditInfo(created_by="test")),
        ])
        repo.update = AsyncMock(return_value=True)
        service = InventoryService(repository=repo)

        from app.application.commerce.dto.commerce_dto import InventoryUpdateDTO
        items = [InventoryUpdateDTO(quantity=10)]
        result = await service.bulk_update("s1", items)
        assert result > 0, (
            f"bulk_update returned {result}. Should return count of updated records."
        )
        repo.update.assert_called_once()

    async def test_order_dto_preserves_line_items_after_get(self, order_service, order_repo):
        audit = AuditInfo(created_by="test")
        now = datetime.now(UTC)
        entity = Order(
            id="ord-2",
            store_id="s1",
            org_id="o1",
            customer_id="c1",
            customer_email="c@example.com",
            line_items=[
                LineItem(
                    id="li-1", variant_id="v1", product_id="p1",
                    title="Item 1", quantity=2,
                    price=Money(amount="10.00", currency="USD"),
                ),
            ],
            financial_status="paid",
            fulfillment_status="fulfilled",
            currency="USD",
            tags=[],
            audit=audit,
            created_at=now,
            updated_at=now,
        )
        order_repo.find_by_id.return_value = entity
        result = await order_service.get_by_id("ord-2")
        assert result.line_items is not None
        assert len(result.line_items) == len(entity.line_items), (
            f"Order DTO should preserve line_items count. "
            f"DTO: {len(result.line_items)}, Entity: {len(entity.line_items)}"
        )
        for li_dto in result.line_items:
            assert li_dto.title
            assert li_dto.price

    async def test_order_to_dto_maps_line_item_fields(self, order_service, order_repo):
        audit = AuditInfo(created_by="test")
        now = datetime.now(UTC)
        entity = Order(
            id="ord-3",
            store_id="s1",
            org_id="o1",
            customer_id="c1",
            customer_email="c@example.com",
            line_items=[
                LineItem(
                    id="li-x", variant_id="vx", product_id="px",
                    title="Test Item", quantity=3,
                    price=Money(amount="15.50", currency="USD"),
                ),
            ],
            financial_status="paid",
            fulfillment_status="fulfilled",
            currency="USD",
            tags=[],
            audit=audit,
            created_at=now,
            updated_at=now,
        )
        order_repo.find_by_id.return_value = entity
        result = await order_service.get_by_id("ord-3")
        li = result.line_items[0]
        assert li.title == "Test Item"
        assert li.quantity == 3
