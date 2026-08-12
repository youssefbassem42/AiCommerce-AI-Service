"""Widget installation document <-> Mongo mapping.

Widget installations use human-readable prefixed ids (``inst_...``) that are
NOT valid Mongo ObjectIds; the base document's ObjectId serialization would
raise ``bson.errors.InvalidId`` on create. These tests pin the override.
"""

from datetime import UTC, datetime

from app.domain.widget.entities.widget_installation import WidgetInstallation
from app.infrastructure.mongodb.documents.widget_installation_document import (
    WidgetInstallationDocument,
)


def _entity() -> WidgetInstallation:
    now = datetime.now(UTC)
    return WidgetInstallation(
        id="inst_5dc6dfb0b71e49b6aa30f92367edb921",
        widget_id="wid_test123456",
        store_id="store-1",
        organization_id="org-1",
        public_key_hash="a" * 64,
        environment="live",
        status="active",
        allowed_origins=["https://store.example.com"],
        scopes=["rag:chat"],
        last_used_at=None,
        created_at=now,
        updated_at=now,
    )


def test_to_mongo_dict_keeps_string_id():
    doc = WidgetInstallationDocument.from_entity(_entity())
    data = doc.to_mongo_dict()
    assert data["_id"] == "inst_5dc6dfb0b71e49b6aa30f92367edb921"
    assert isinstance(data["_id"], str)


def test_round_trip_preserves_id():
    doc = WidgetInstallationDocument.from_entity(_entity())
    restored = WidgetInstallationDocument.from_mongo_dict(doc.to_mongo_dict())
    assert restored.id == "inst_5dc6dfb0b71e49b6aa30f92367edb921"
    assert restored.to_entity().id == "inst_5dc6dfb0b71e49b6aa30f92367edb921"
    assert restored.widget_id == "wid_test123456"


def test_from_mongo_dict_accepts_object_id_id():
    from bson import ObjectId

    doc = WidgetInstallationDocument.from_entity(_entity())
    data = doc.to_mongo_dict()
    data["_id"] = ObjectId()
    restored = WidgetInstallationDocument.from_mongo_dict(data)
    assert restored.id == str(data["_id"])
