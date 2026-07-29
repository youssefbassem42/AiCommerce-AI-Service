from datetime import datetime, timezone

import pydantic
import pytest

from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.exceptions import IntegrationValidationException
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle


def _make_connection(**overrides) -> IntegrationConnection:
    base = dict(
        id="conn1",
        store_id="store_1",
        organization_id="org_1",
        name="My Shopify Store",
        platform_name="shopify",
    )
    base.update(overrides)
    return IntegrationConnection(**base)


class TestIntegrationConnectionCreation:
    def test_create_minimal_connection(self) -> None:
        conn = _make_connection()
        assert conn.store_id == "store_1"
        assert conn.name == "My Shopify Store"
        assert conn.status == ConnectionStatus.INACTIVE
        assert conn.spec_version == "3.0"
        assert conn.encrypted_credentials is None
        assert conn.entity_mappings == []
        assert conn.discovered_endpoints == []
        assert conn.error_message is None
        assert conn.last_sync_at is None

    def test_empty_name_raises(self) -> None:
        with pytest.raises(IntegrationValidationException):
            _make_connection(name="   ")

    def test_required_store_id(self) -> None:
        with pytest.raises((IntegrationValidationException, pydantic.ValidationError)):
            IntegrationConnection(
                id="c1",
                store_id="",
                organization_id="org1",
                name="test",
                platform_name="shopify",
            )

    def test_status_enum_values(self) -> None:
        conn = _make_connection()
        assert conn.status in (ConnectionStatus.ACTIVE, ConnectionStatus.INACTIVE, ConnectionStatus.ERROR)

    def test_audit_info_present(self) -> None:
        conn = _make_connection()
        assert conn.audit is not None
        assert conn.audit.created_at is not None


class TestIntegrationConnectionMethods:
    def test_update_spec(self) -> None:
        conn = _make_connection()
        conn.update_spec("3.0", {"openapi": "3.0.0"}, [{"path": "/products"}], {"Product": {}})
        assert conn.spec_version == "3.0"
        assert conn.discovered_endpoints == [{"path": "/products"}]
        assert conn.discovered_schemas == {"Product": {}}

    def test_set_credentials(self) -> None:
        conn = _make_connection()
        auth = AuthConfig(type=AuthType.APIKEY, name="X-Key")
        conn.set_credentials(auth, "encrypted_blob")
        assert conn.auth_config.type == AuthType.APIKEY
        assert conn.encrypted_credentials == "encrypted_blob"

    def test_update_mappings_replaces_all(self) -> None:
        conn = _make_connection()
        mappings = [
            EntityMapping(entity_type="product", list_path="/products", id_field="id"),
        ]
        conn.update_mappings(mappings)
        assert len(conn.entity_mappings) == 1
        assert conn.entity_mappings[0].entity_type == "product"

    def test_replace_entity_mapping_adds_new(self) -> None:
        conn = _make_connection()
        m1 = EntityMapping(entity_type="product", list_path="/products", id_field="id")
        m2 = EntityMapping(entity_type="order", list_path="/orders", id_field="id")
        conn.replace_entity_mapping(m1)
        conn.replace_entity_mapping(m2)
        assert len(conn.entity_mappings) == 2

    def test_replace_entity_mapping_updates_existing(self) -> None:
        conn = _make_connection()
        m1 = EntityMapping(entity_type="product", list_path="/products", id_field="id")
        m2 = EntityMapping(entity_type="product", list_path="/v2/products", id_field="id")
        conn.replace_entity_mapping(m1)
        conn.replace_entity_mapping(m2)
        assert len(conn.entity_mappings) == 1
        assert conn.entity_mappings[0].list_path == "/v2/products"

    def test_remove_entity_mapping(self) -> None:
        conn = _make_connection()
        conn.replace_entity_mapping(
            EntityMapping(entity_type="product", list_path="/products", id_field="id")
        )
        conn.remove_entity_mapping("product")
        assert len(conn.entity_mappings) == 0

    def test_remove_nonexistent_mapping_raises(self) -> None:
        conn = _make_connection()
        with pytest.raises(IntegrationValidationException):
            conn.remove_entity_mapping("nonexistent")

    def test_mark_synced(self) -> None:
        conn = _make_connection()
        conn.set_credentials(AuthConfig(type=AuthType.APIKEY, name="X-Key"), "enc")
        conn.activate()
        conn.mark_synced("success")
        assert conn.last_sync_status == "success"
        assert conn.last_sync_at is not None
        assert conn.error_message is None

    def test_mark_error(self) -> None:
        conn = _make_connection()
        conn.set_credentials(AuthConfig(type=AuthType.APIKEY, name="X-Key"), "enc")
        conn.activate()
        conn.mark_error("Connection refused")
        assert conn.status == ConnectionStatus.ERROR
        assert conn.error_message == "Connection refused"

    def test_mark_synced_on_inactive_raises(self) -> None:
        conn = _make_connection()
        with pytest.raises(IntegrationValidationException):
            conn.mark_synced()

    def test_mark_error_on_inactive_raises(self) -> None:
        conn = _make_connection()
        with pytest.raises(IntegrationValidationException):
            conn.mark_error("fail")

    def test_activate_without_credentials_raises(self) -> None:
        conn = _make_connection()
        with pytest.raises(IntegrationValidationException):
            conn.activate()

    def test_activate(self) -> None:
        conn = _make_connection()
        conn.set_credentials(AuthConfig(type=AuthType.APIKEY, name="X-Key"), "enc")
        conn.activate()
        assert conn.status == ConnectionStatus.ACTIVE

    def test_deactivate(self) -> None:
        conn = _make_connection()
        conn.set_credentials(AuthConfig(type=AuthType.APIKEY, name="X-Key"), "enc")
        conn.activate()
        conn.deactivate()
        assert conn.status == ConnectionStatus.INACTIVE


class TestIntegrationConnectionValueObjects:
    def test_auth_config_api_key_requires_name(self) -> None:
        AuthConfig(type=AuthType.APIKEY, name="X-Key")
        with pytest.raises(ValueError):
            AuthConfig(type=AuthType.APIKEY, name="")

    def test_auth_config_bearer_requires_scheme(self) -> None:
        AuthConfig(type=AuthType.BEARER, scheme="bearer")
        with pytest.raises(ValueError):
            AuthConfig(type=AuthType.BEARER, scheme="")

    def test_auth_config_oauth2_requires_token_url(self) -> None:
        with pytest.raises(ValueError):
            AuthConfig(type=AuthType.OAUTH2, token_url="")

    def test_entity_mapping_requires_path(self) -> None:
        with pytest.raises(ValueError):
            EntityMapping(entity_type="product", list_path="", detail_path="", id_field="id")

    def test_pagination_config_defaults(self) -> None:
        pc = PaginationConfig()
        assert pc.style == PaginationStyle.NONE
        assert pc.default_limit == 20

    def test_field_mapping_minimal(self) -> None:
        fm = FieldMapping(source="name", target="title")
        assert fm.source == "name"
        assert fm.target == "title"
        assert fm.required is False
        assert fm.transformer is None