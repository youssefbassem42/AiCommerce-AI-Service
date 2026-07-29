from datetime import datetime, UTC

from app.domain.commerce.events.product_events import (
    ProductCreated,
    ProductUpdated,
    ProductDeleted,
    ProductSynced,
)
from app.domain.commerce.events.order_events import OrderPlaced, OrderUpdated, OrderCancelled
from app.domain.commerce.events.customer_events import CustomerCreated, CustomerUpdated
from app.domain.commerce.events.inventory_events import InventoryChanged, StockAlert


class TestProductEvents:
    def test_product_created(self):
        event = ProductCreated(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            external_id="ext-1",
        )
        assert event.product_id == "prod-1"
        assert event.store_id == "store-1"
        assert event.organization_id == "org-1"
        assert event.external_id == "ext-1"
        assert event.event_id is not None
        assert event.occurred_at is not None

    def test_product_updated(self):
        event = ProductUpdated(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            changed_fields=["name", "price"],
        )
        assert "name" in event.changed_fields
        assert "price" in event.changed_fields

    def test_product_deleted(self):
        event = ProductDeleted(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
        )
        assert event.product_id == "prod-1"

    def test_product_synced(self):
        event = ProductSynced(
            product_id="prod-1",
            store_id="store-1",
            organization_id="org-1",
            platform="shopify",
            sync_session_id="sync-123",
        )
        assert event.platform == "shopify"
        assert event.sync_session_id == "sync-123"


class TestOrderEvents:
    def test_order_placed(self):
        event = OrderPlaced(
            order_id="ord-1",
            store_id="store-1",
            organization_id="org-1",
            customer_id="cust-1",
            total=99.99,
        )
        assert event.order_id == "ord-1"
        assert event.total == 99.99

    def test_order_updated(self):
        event = OrderUpdated(
            order_id="ord-1",
            store_id="store-1",
            organization_id="org-1",
            changed_fields=["status"],
        )
        assert "status" in event.changed_fields

    def test_order_cancelled(self):
        event = OrderCancelled(
            order_id="ord-1",
            store_id="store-1",
            organization_id="org-1",
        )
        assert event.order_id == "ord-1"


class TestCustomerEvents:
    def test_customer_created(self):
        event = CustomerCreated(
            customer_id="cust-1",
            store_id="store-1",
            organization_id="org-1",
            email="test@example.com",
        )
        assert event.email == "test@example.com"

    def test_customer_updated(self):
        event = CustomerUpdated(
            customer_id="cust-1",
            store_id="store-1",
            organization_id="org-1",
            changed_fields=["email"],
        )
        assert "email" in event.changed_fields


class TestInventoryEvents:
    def test_inventory_changed(self):
        event = InventoryChanged(
            product_id="prod-1",
            variant_id="var-1",
            store_id="store-1",
            organization_id="org-1",
            old_quantity=10,
            new_quantity=5,
        )
        assert event.old_quantity == 10
        assert event.new_quantity == 5

    def test_stock_alert(self):
        event = StockAlert(
            product_id="prod-1",
            variant_id="var-1",
            store_id="store-1",
            organization_id="org-1",
            current_quantity=3,
            threshold=5,
        )
        assert event.current_quantity == 3
        assert event.threshold == 5
