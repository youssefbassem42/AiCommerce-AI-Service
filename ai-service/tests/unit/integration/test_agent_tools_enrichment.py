from app.agents.integration.schemas import (
    AuthInfo,
    DiscoveredEntityInfo,
    FeatureAnalysis,
    IntegrationMappingReport,
)
from app.agents.integration.tools import _enrich_report_field_mappings, _response_item_fields

SPEC = {
    "paths": {
        "/api/Products": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/GeneralResponseProductList"}}
                        }
                    }
                }
            }
        },
        "/api/admin/users": {
            "get": {
                "responses": {
                    "200": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/UserList"}}}}
                }
            }
        },
    },
    "components": {
        "schemas": {
            "GeneralResponseProductList": {
                "type": "object",
                "properties": {"data": {"type": "array", "items": {"$ref": "#/components/schemas/ProductDto"}}},
            },
            "ProductDto": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "stockQuantity": {"type": "integer"},
                    "categoryName": {"type": "string"},
                },
            },
            "UserList": {
                "type": "object",
                "properties": {"data": {"type": "array", "items": {"$ref": "#/components/schemas/UserDto"}}},
            },
            "UserDto": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "email": {"type": "string"},
                    "firstName": {"type": "string"},
                    "lastName": {"type": "string"},
                    "phoneNumber": {"type": "string"},
                },
            },
        }
    },
}


def _entity(entity_type: str, list_path: str) -> DiscoveredEntityInfo:
    return DiscoveredEntityInfo(
        entity_type=entity_type,
        display_name=entity_type.title(),
        description="test",
        list_path=list_path,
    )


def _report(*entities: DiscoveredEntityInfo) -> IntegrationMappingReport:
    return IntegrationMappingReport(
        platform_name="test",
        base_url="https://example.com",
        api_version="3.0",
        entities=list(entities),
        auth=AuthInfo(),
        feature_analysis=FeatureAnalysis(),
    )


def test_response_item_fields_resolves_ref() -> None:
    fields = _response_item_fields(SPEC, "/api/Products")
    assert "name" in fields
    assert "price" in fields
    assert "stockQuantity" in fields


def test_response_item_fields_unknown_path() -> None:
    assert _response_item_fields(SPEC, "/nope") == set()


def test_enrich_fills_empty_order_mappings_camelcase() -> None:
    report = _report(_entity("customer", "/api/admin/users"))
    enriched = _enrich_report_field_mappings(report, SPEC)
    entity = enriched.entities[0]
    assert entity.field_mappings, "empty mappings must be backfilled"
    targets = {fm.target for fm in entity.field_mappings}
    assert "email" in targets
    assert "first_name" in targets
    assert "last_name" in targets
    assert any(w.startswith("Backfilled field mappings") for w in enriched.warnings)


def test_enrich_keeps_existing_mappings_untouched() -> None:
    from app.agents.integration.schemas import FieldMappingInfo

    entity = _entity("product", "/api/Products")
    entity.field_mappings = [FieldMappingInfo(source="name", target="title")]
    report = _report(entity)
    enriched = _enrich_report_field_mappings(report, SPEC)
    assert len(enriched.entities[0].field_mappings) == 1
    assert enriched.entities[0].field_mappings[0].target == "title"


def test_enrich_ignores_entities_without_list_path() -> None:
    entity = _entity("order", "")
    entity.list_path = None
    report = _report(entity)
    enriched = _enrich_report_field_mappings(report, SPEC)
    assert enriched.entities[0].field_mappings == []
