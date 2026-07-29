import pytest

from app.domain.recommendation.entities.store_capabilities import StoreCapabilities


@pytest.mark.unit
class TestStoreCapabilities:
    def test_default_capabilities(self):
        caps = StoreCapabilities(id="c1", store_id="store_1")
        assert caps.store_id == "store_1"
        assert caps.capabilities == {"has_promo_codes": False}
        assert caps.auto_detected == {}

    def test_get_returns_default(self):
        caps = StoreCapabilities(id="c1", store_id="store_1")
        assert caps.get("has_promo_codes") is False
        assert caps.get("nonexistent", True) is True

    def test_set_capability_manual(self):
        caps = StoreCapabilities(id="c1", store_id="store_1")
        caps.set_capability("has_promo_codes", True, is_auto_detected=False)
        assert caps.get("has_promo_codes") is True
        assert caps.auto_detected["has_promo_codes"] is False

    def test_set_capability_auto(self):
        caps = StoreCapabilities(id="c1", store_id="store_1")
        caps.set_capability("has_promo_codes", True, is_auto_detected=True)
        assert caps.auto_detected["has_promo_codes"] is True

    def test_updated_at_changes_on_set(self):
        caps = StoreCapabilities(id="c1", store_id="store_1")
        original = caps.updated_at
        caps.set_capability("has_promo_codes", True)
        assert caps.updated_at >= original

    def test_equality_by_id(self):
        caps1 = StoreCapabilities(id="same", store_id="store_1")
        caps2 = StoreCapabilities(id="same", store_id="store_2")
        assert caps1 == caps2
        assert hash(caps1) == hash(caps2)

    def test_inequality(self):
        caps1 = StoreCapabilities(id="a", store_id="store_1")
        caps2 = StoreCapabilities(id="b", store_id="store_1")
        assert caps1 != caps2
