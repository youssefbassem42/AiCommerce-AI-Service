import pytest
from bson import ObjectId

from app.domain.recommendation.entities.store_capabilities import StoreCapabilities
from app.infrastructure.mongodb.documents.store_capabilities_document import (
    StoreCapabilitiesDocument,
)

VALID_OID = str(ObjectId())


@pytest.mark.unit
class TestStoreCapabilitiesDocument:
    def test_to_entity_roundtrip(self):
        doc = StoreCapabilitiesDocument(
            _id=VALID_OID,
            store_id="store_1",
            capabilities={"has_promo_codes": True},
            auto_detected={"has_promo_codes": True},
        )
        entity = doc.to_entity()
        assert entity.store_id == "store_1"
        assert entity.capabilities == {"has_promo_codes": True}
        assert entity.auto_detected == {"has_promo_codes": True}

    def test_from_entity_roundtrip(self):
        entity = StoreCapabilities(
            id=VALID_OID,
            store_id="store_1",
            capabilities={"has_promo_codes": False},
            auto_detected={},
        )
        doc = StoreCapabilitiesDocument.from_entity(entity)
        assert doc.store_id == "store_1"
        assert doc.capabilities == {"has_promo_codes": False}
        assert doc.auto_detected == {}

    def test_full_roundtrip(self):
        entity = StoreCapabilities(
            id=VALID_OID,
            store_id="store_1",
            capabilities={"has_promo_codes": True},
            auto_detected={"has_promo_codes": True},
        )
        doc = StoreCapabilitiesDocument.from_entity(entity)
        restored = doc.to_entity()
        assert restored.store_id == entity.store_id
        assert restored.capabilities == entity.capabilities
        assert restored.auto_detected == entity.auto_detected
