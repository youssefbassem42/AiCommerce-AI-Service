import pytest

from app.domain.commerce.aggregates.category import Category


class TestCategory:

    def test_valid_category(self):
        cat = Category(
            id="c1",
            store_id="store1",
            org_id="org1",
            name="Electronics",
        )
        assert cat.name == "Electronics"
        assert cat.sort_order == 0
        assert cat.product_count == 0

    def test_with_parent(self):
        cat = Category(
            id="c2",
            store_id="store1",
            org_id="org1",
            name="Laptops",
            parent_id="c1",
            sort_order=1,
        )
        assert cat.parent_id == "c1"
        assert cat.sort_order == 1

    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Category(
                id="c1",
                store_id="store1",
                org_id="org1",
                name="",
            )

    def test_negative_product_count_raises(self):
        with pytest.raises(ValueError):
            Category(
                id="c1",
                store_id="store1",
                org_id="org1",
                name="Test",
                product_count=-1,
            )

    def test_external_id(self):
        cat = Category(
            id="c1",
            store_id="store1",
            org_id="org1",
            external_id="ext-cat-1",
            name="Test",
        )
        assert cat.external_id == "ext-cat-1"

    def test_default_values(self):
        cat = Category(
            id="c1",
            store_id="store1",
            org_id="org1",
            name="Test",
        )
        assert cat.description is None
        assert cat.handle is None
        assert cat.parent_id is None
        assert cat.image_url is None
