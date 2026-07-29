import pytest

from app.domain.commerce.entities.inventory import Inventory


class TestInventory:

    def test_valid_inventory(self):
        inv = Inventory(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
        )
        assert inv.quantity == 0
        assert inv.available == 0
        assert inv.committed == 0

    def test_with_values(self):
        inv = Inventory(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            quantity=100,
            available=80,
            committed=20,
            incoming=10,
            low_stock_threshold=10,
        )
        assert inv.quantity == 100
        assert inv.available == 80
        assert inv.incoming == 10

    def test_negative_available_raises(self):
        with pytest.raises(ValueError):
            Inventory(
                id="i1",
                product_id="p1",
                variant_id="v1",
                store_id="store1",
                org_id="org1",
                available=-1,
            )

    def test_negative_committed_raises(self):
        with pytest.raises(ValueError):
            Inventory(
                id="i1",
                product_id="p1",
                variant_id="v1",
                store_id="store1",
                org_id="org1",
                committed=-1,
            )

    def test_external_id(self):
        inv = Inventory(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            external_id="ext-inv-1",
        )
        assert inv.external_id == "ext-inv-1"

    def test_location(self):
        inv = Inventory(
            id="i1",
            product_id="p1",
            variant_id="v1",
            store_id="store1",
            org_id="org1",
            location_id="loc1",
            location_name="Warehouse A",
        )
        assert inv.location_id == "loc1"
        assert inv.location_name == "Warehouse A"
