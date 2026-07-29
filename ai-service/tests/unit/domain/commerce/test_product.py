from decimal import Decimal

import pytest

from app.domain.commerce.aggregates.product import Product, Variant
from app.domain.commerce.value_objects.money import Money


class TestProductCreation:

    def test_valid_product(self):
        product = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Test Product",
        )
        assert product.id == "p1"
        assert product.title == "Test Product"
        assert product.status == "draft"

    def test_invalid_status(self):
        with pytest.raises(ValueError, match="Status must be one of"):
            Product(
                id="p1",
                store_id="store1",
                organization_id="org1",
                title="Test",
                status="invalid",
            )

    def test_active_status_allowed(self):
        product = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Test",
            status="active",
        )
        assert product.status == "active"

    def test_archived_status_allowed(self):
        product = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Test",
            status="archived",
        )
        assert product.status == "archived"

    def test_empty_title_raises(self):
        with pytest.raises(ValueError):
            Product(
                id="p1",
                store_id="store1",
                organization_id="org1",
                title="",
            )

    def test_optional_fields_default(self):
        product = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            title="Test",
        )
        assert product.tags == []
        assert product.images == []
        assert product.variants == []
        assert product.metadata == {}

    def test_full_product(self):
        product = Product(
            id="p1",
            store_id="store1",
            organization_id="org1",
            external_id="ext-1",
            title="Full Product",
            description="A full product",
            handle="full-product",
            status="active",
            product_type="physical",
            vendor="TestVendor",
            tags=["tag1", "tag2"],
            category_id="cat1",
        )
        assert product.external_id == "ext-1"
        assert product.handle == "full-product"
        assert product.product_type == "physical"
        assert product.vendor == "TestVendor"


class TestProductVariantManagement:

    def test_add_variant(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        variant = Variant(
            id="v1",
            sku="SKU-001",
            title="Variant 1",
            price=Money(amount=Decimal("10"), currency="USD"),
        )
        product.add_variant(variant)
        assert len(product.variants) == 1
        assert product.variants[0].sku == "SKU-001"

    def test_add_duplicate_sku_raises(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        v2 = Variant(id="v2", sku="SKU-001", title="V2", price=Money(amount=Decimal("20"), currency="USD"))
        product.add_variant(v1)
        with pytest.raises(ValueError, match="SKU 'SKU-001' already exists"):
            product.add_variant(v2)

    def test_remove_variant(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        v2 = Variant(id="v2", sku="SKU-002", title="V2", price=Money(amount=Decimal("20"), currency="USD"))
        product.add_variant(v1)
        product.add_variant(v2)
        product.remove_variant("v1")
        assert len(product.variants) == 1
        assert product.variants[0].id == "v2"

    def test_remove_nonexistent_variant(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        product.remove_variant("nonexistent")
        assert len(product.variants) == 0

    def test_update_price(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        product.add_variant(v1)
        product.update_price("v1", Money(amount=Decimal("25"), currency="USD"))
        assert product.variants[0].price.amount == Decimal("25")

    def test_update_price_nonexistent_variant(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        with pytest.raises(ValueError, match="Variant with id 'v99' not found"):
            product.update_price("v99", Money(amount=Decimal("10"), currency="USD"))

    def test_update_inventory(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        product.add_variant(v1)
        product.update_inventory("v1", 50)
        assert product.variants[0].inventory_quantity == 50

    def test_update_inventory_zero(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        product.add_variant(v1)
        product.update_inventory("v1", 0)
        assert product.variants[0].inventory_quantity == 0

    def test_update_inventory_negative_raises(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        v1 = Variant(id="v1", sku="SKU-001", title="V1", price=Money(amount=Decimal("10"), currency="USD"))
        product.add_variant(v1)
        with pytest.raises(ValueError, match="Inventory quantity cannot be negative"):
            product.update_inventory("v1", -1)


class TestProductStatusTransitions:

    def test_activate(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        assert product.status == "draft"
        product.activate()
        assert product.status == "active"

    def test_archive(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test")
        product.archive()
        assert product.status == "archived"

    def test_activate_from_archived(self):
        product = Product(id="p1", store_id="s1", organization_id="o1", title="Test", status="archived")
        product.activate()
        assert product.status == "active"
