from decimal import Decimal

import pytest

from app.domain.commerce.aggregates.order import LineItem, Order, TaxLine
from app.domain.commerce.value_objects.money import Money


class TestOrder:

    def test_valid_order(self):
        order = Order(
            id="o1",
            store_id="store1",
            org_id="org1",
            customer_id="c1",
            customer_email="test@example.com",
        )
        assert order.financial_status == "pending"
        assert order.currency == "USD"
        assert order.cancelled_at is None

    def test_with_line_items(self):
        item = LineItem(
            id="li1",
            title="Test Item",
            quantity=2,
            price=Money(amount=Decimal("10"), currency="USD"),
        )
        order = Order(
            id="o1",
            store_id="store1",
            org_id="org1",
            line_items=[item],
        )
        assert len(order.line_items) == 1
        assert order.line_items[0].title == "Test Item"
        assert order.line_items[0].quantity == 2

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            LineItem(
                id="li1",
                title="Item",
                quantity=0,
                price=Money(amount=Decimal("10"), currency="USD"),
            )

    def test_order_with_tags(self):
        order = Order(
            id="o1",
            store_id="store1",
            org_id="org1",
            tags=["urgent", "priority"],
        )
        assert "urgent" in order.tags
        assert len(order.tags) == 2

    def test_order_with_tax_lines(self):
        item = LineItem(
            id="li1",
            title="Item",
            quantity=1,
            price=Money(amount=Decimal("100"), currency="USD"),
            tax_lines=[
                TaxLine(id="tx1", title="VAT", rate=0.2, price=Money(amount=Decimal("20"), currency="USD")),
            ],
        )
        assert len(item.tax_lines) == 1
        assert item.tax_lines[0].rate == 0.2

    def test_external_id(self):
        order = Order(
            id="o1",
            store_id="store1",
            org_id="org1",
            external_id="ext-order-1",
        )
        assert order.external_id == "ext-order-1"

    def test_empty_store_id_raises(self):
        with pytest.raises(ValueError):
            Order(id="o1", store_id="", org_id="org1")
