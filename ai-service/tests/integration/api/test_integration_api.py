from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth.dependencies import require_admin_role
from app.api.integration.dependencies import (
    get_ecommerce_authenticator,
    get_integration_service,
    get_integration_workflow,
    get_sync_orchestrator,
)
from app.application.integration.sync.orchestrator import SyncResult
from app.domain.integration.exceptions import IntegrationAuthenticationError
from app.main import app
from app.middleware.audit import AuditMiddleware
from tests.conftest import admin_headers

OPENAPI_V3_MINIMAL = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "servers": [{"url": "https://api.test.com"}],
    "paths": {
        "/products": {
            "get": {
                "summary": "List products",
                "operationId": "listProducts",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
    "components": {
        "schemas": {
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "price": {"type": "number"},
                },
            }
        }
    },
}

ECOMMERCE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "E-Commerce API", "version": "1.0.0"},
    "servers": [{"url": "https://api.shop.com"}],
    "paths": {
        "/api/Auth/login": {
            "post": {
                "summary": "Login user and obtain JWT token",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/products": {
            "get": {
                "summary": "List products",
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}

STORE_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(app, raise_server_exceptions=False, headers=admin_headers(store_id=STORE_ID))


def connection_dto(**overrides):
    base = {
        "id": "conn1",
        "store_id": STORE_ID,
        "organization_id": "o1",
        "name": "Test",
        "platform_name": "shopify",
        "status": "active",
        "spec_version": "3.0",
        "auth_config": {
            "type": "apiKey",
            "credentials_location": "header",
            "scheme": None,
            "name": "X-API-Key",
            "token_url": None,
            "flow": None,
        },
        "entity_mappings": [],
        "discovered_endpoints": [],
        "discovered_schemas": {},
        "raw_spec": None,
        "last_sync_at": None,
        "last_sync_status": None,
        "error_message": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    base.update(overrides)
    obj = MagicMock()
    obj.model_dump = MagicMock(return_value=base)
    obj.store_id = base["store_id"]
    obj.id = base["id"]
    obj.raw_spec = base["raw_spec"]
    return obj


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.parse_spec = AsyncMock()
    svc.create_connection = AsyncMock()
    svc.list_connections = AsyncMock()
    svc.get_connection = AsyncMock()
    svc.update_mappings = AsyncMock()
    svc.update_credentials = AsyncMock()
    svc.delete_connection = AsyncMock()
    return svc


@pytest.fixture
def mock_sync_orchestrator():
    orch = MagicMock()
    orch.sync_connection = AsyncMock()
    return orch


@pytest.fixture
def mock_authenticator():
    auth = MagicMock()
    auth.login = AsyncMock(return_value="ecomm-token")
    return auth


@pytest.fixture
def mock_workflow():
    wf = MagicMock()
    wf.run = AsyncMock()
    return wf


@pytest.fixture
def claims_client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(
            app,
            raise_server_exceptions=False,
            headers=admin_headers(
                store_id=STORE_ID,
                store_admin_email="admin@shop.com",
                store_admin_password="Test@123",
            ),
        )


@pytest.fixture
def override_deps(client, mock_service, mock_sync_orchestrator):
    app.dependency_overrides[get_integration_service] = lambda: mock_service
    app.dependency_overrides[get_sync_orchestrator] = lambda: mock_sync_orchestrator
    app.dependency_overrides[require_admin_role] = lambda: None
    yield
    app.dependency_overrides.pop(get_integration_service, None)
    app.dependency_overrides.pop(get_sync_orchestrator, None)
    app.dependency_overrides.pop(require_admin_role, None)


@pytest.fixture
def override_deps_with_auth(override_deps, mock_authenticator):
    app.dependency_overrides[get_ecommerce_authenticator] = lambda: mock_authenticator
    yield override_deps
    app.dependency_overrides.pop(get_ecommerce_authenticator, None)


@pytest.fixture
def override_workflow(client, mock_workflow):
    app.dependency_overrides[get_integration_workflow] = lambda: mock_workflow
    yield mock_workflow
    app.dependency_overrides.pop(get_integration_workflow, None)


class TestIntegrationAPI:
    def test_parse_spec(self, client, mock_service, override_deps):
        mock_service.parse_spec.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "platform_name": "shopify",
                    "base_url": "https://api.test.com",
                    "api_version": "3.0",
                    "endpoints": [],
                    "schemas": {},
                    "auth_methods": [],
                    "discovered_entities": [],
                    "suggested_mappings": [],
                    "warnings": [],
                    "errors": [],
                }
            )
        )
        resp = client.post(
            "/api/v1/integration/schemas/parse",
            json={
                "platform_name": "shopify",
                "raw_spec": OPENAPI_V3_MINIMAL,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform_name"] == "shopify"
        assert data["base_url"] == "https://api.test.com"

    def test_parse_spec_invalid(self, client, mock_service, override_deps):
        from app.domain.integration.exceptions import InvalidSpecException

        mock_service.parse_spec.side_effect = InvalidSpecException("Invalid spec")
        resp = client.post(
            "/api/v1/integration/schemas/parse",
            json={
                "platform_name": "shopify",
                "raw_spec": {"invalid": True},
            },
        )
        assert resp.status_code in (400, 422)

    def test_create_connection(self, client, mock_service, override_deps):
        mock_service.create_connection.return_value = MagicMock(
            model_dump=MagicMock(
                return_value={
                    "id": "conn1",
                    "store_id": "s1",
                    "organization_id": "o1",
                    "name": "Test Connection",
                    "platform_name": "shopify",
                    "status": "active",
                    "spec_version": "3.0",
                    "auth_config": {
                        "type": "apiKey",
                        "credentials_location": "header",
                        "scheme": None,
                        "name": "X-API-Key",
                        "token_url": None,
                        "flow": None,
                    },
                    "entity_mappings": [],
                    "discovered_endpoints": [],
                    "discovered_schemas": {},
                    "last_sync_at": None,
                    "last_sync_status": None,
                    "error_message": None,
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            )
        )
        resp = client.post(
            "/api/v1/integration/connections",
            json={
                "store_id": "s1",
                "name": "Test Connection",
                "platform_name": "shopify",
                "raw_spec": OPENAPI_V3_MINIMAL,
                "auth_config": {"type": "apiKey", "name": "X-API-Key"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Test Connection"

    def test_list_connections(self, client, mock_service, override_deps):
        mock_service.list_connections = AsyncMock(return_value=([], 0))
        resp = client.get("/api/v1/integration/connections?store_id=s1")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_get_connection(self, client, mock_service, override_deps):
        mock_service.get_connection = AsyncMock(return_value=connection_dto())
        resp = client.get("/api/v1/integration/connections/conn1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "conn1"

    def test_get_connection_cross_store_denied(self, client, mock_service, override_deps):
        mock_service.get_connection = AsyncMock(
            return_value=connection_dto(store_id="22222222-2222-2222-2222-222222222222")
        )
        resp = client.get("/api/v1/integration/connections/conn1")
        assert resp.status_code == 404

    def test_sync_connection(self, client, mock_service, mock_sync_orchestrator, override_deps):
        result = SyncResult(connection_id="conn1", store_id="s1")
        result.status = "completed"
        result.completed_at = result.started_at
        mock_service.get_connection = AsyncMock(return_value=connection_dto())
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=result)

        resp = client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["connection_id"] == "conn1"
        assert data["status"] == "completed"
        assert "started_at" in data

    def test_sync_connection_error_surfaces_500(self, client, mock_service, mock_sync_orchestrator, override_deps):
        """REGRESSION: a sync that failed (e.g. deleted e-commerce account —
        every endpoint rejected) must not come back as a silent 200."""
        result = SyncResult(connection_id="conn1", store_id="s1")
        result.status = "error"
        result.error = (
            "Sync completed but no data was fetched — every endpoint failed "
            "(first error: Skipped: endpoint requires admin authentication (HTTP 401))."
        )
        result.completed_at = result.started_at
        mock_service.get_connection = AsyncMock(return_value=connection_dto())
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=result)

        resp = client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 500
        assert "no data was fetched" in resp.json()["detail"]

    def test_sync_connection_not_found(self, client, mock_service, mock_sync_orchestrator, override_deps):
        from app.domain.integration.exceptions import IntegrationConnectionNotFoundException

        mock_service.get_connection = AsyncMock(side_effect=IntegrationConnectionNotFoundException("conn1"))
        resp = client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 404

    def test_update_mappings(self, client, mock_service, override_deps):
        mock_service.get_connection = AsyncMock(return_value=connection_dto())
        mock_service.update_mappings = AsyncMock(
            return_value=connection_dto(
                entity_mappings=[
                    {
                        "entity_type": "product",
                        "list_path": "/products.json",
                        "list_method": "GET",
                        "detail_path": None,
                        "detail_method": "GET",
                        "id_field": "id",
                        "pagination": {
                            "style": "none",
                            "page_param": None,
                            "limit_param": None,
                            "default_limit": 20,
                            "cursor_field": None,
                            "total_field": None,
                            "next_link_field": None,
                        },
                        "field_mappings": [],
                    }
                ]
            )
        )
        resp = client.put(
            "/api/v1/integration/connections/conn1/mappings",
            json={
                "entity_mappings": [
                    {
                        "entity_type": "product",
                        "list_path": "/products.json",
                        "id_field": "id",
                        "field_mappings": [],
                    }
                ],
            },
        )
        assert resp.status_code == 200

    def test_delete_connection(self, client, mock_service, override_deps):
        mock_service.get_connection = AsyncMock(return_value=connection_dto())
        mock_service.delete_connection = AsyncMock(return_value=True)
        resp = client.delete("/api/v1/integration/connections/conn1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True


class TestAgentSyncSurfacesFailures:
    def test_agent_sync_error_returns_500(self, client, override_workflow):
        """REGRESSION: a failed full integration (e.g. deleted e-commerce
        account) must surface as a failure — not a 200 with errors buried in
        the body (the 'all 200 codes but nothing happened' bug)."""
        from app.workflows.integration.graph import IntegrationSyncResult

        result = IntegrationSyncResult()
        result.connection_id = "conn1"
        result.error = (
            "Sync completed but no data was fetched — every endpoint failed "
            "(first error: Skipped: endpoint requires admin authentication (HTTP 401))."
        )
        result.user_friendly_error = result.error
        result.sync_result = {"status": "error", "error": result.error}
        result.completed_at = result.started_at
        override_workflow.run = AsyncMock(return_value=result)

        resp = client.post(
            "/api/v1/integration/agent-sync",
            json={
                "platform_name": "ecommerce",
                "raw_spec": ECOMMERCE_SPEC,
                "store_id": STORE_ID,
                "credentials": {"email": "deleted@shop.com", "password": "old-password"},
            },
        )
        assert resp.status_code == 500
        assert "no data was fetched" in resp.json()["detail"]

    def test_agent_sync_success_returns_200(self, client, override_workflow):
        from app.workflows.integration.graph import IntegrationSyncResult

        result = IntegrationSyncResult()
        result.connection_id = "conn1"
        result.sync_result = {"status": "completed", "entity_results": [], "error": None}
        result.completed_at = result.started_at
        override_workflow.run = AsyncMock(return_value=result)

        resp = client.post(
            "/api/v1/integration/agent-sync",
            json={
                "platform_name": "ecommerce",
                "raw_spec": ECOMMERCE_SPEC,
                "store_id": STORE_ID,
                "credentials": {"email": "a@shop.com", "password": "p"},
            },
        )
        assert resp.status_code == 200


class TestSyncNowLoginGate:
    def create_payload(self, raw_spec=ECOMMERCE_SPEC):
        return {
            "store_id": STORE_ID,
            "name": "E-Commerce",
            "platform_name": "ecommerce",
            "raw_spec": raw_spec,
            "auth_config": {"type": "bearer", "name": "Authorization"},
        }

    def test_create_connection_logs_in_before_create(
        self, claims_client, mock_service, mock_authenticator, override_deps_with_auth
    ):
        mock_service.create_connection = AsyncMock(return_value=connection_dto(name="E-Commerce"))
        resp = claims_client.post("/api/v1/integration/connections", json=self.create_payload())
        assert resp.status_code == 201
        mock_authenticator.login.assert_awaited_once()
        _, kwargs = mock_service.create_connection.call_args
        assert kwargs.get("replace_existing") is True

    def test_create_connection_login_failure_creates_and_runs_public_fallback(
        self, claims_client, mock_service, mock_sync_orchestrator, mock_authenticator, override_deps_with_auth
    ):
        mock_authenticator.login = AsyncMock(side_effect=IntegrationAuthenticationError())
        mock_service.create_connection = AsyncMock(return_value=connection_dto(name="E-Commerce"))
        fallback = SyncResult(connection_id="conn1", store_id=STORE_ID)
        fallback.status = "completed"
        fallback.completed_at = fallback.started_at
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=fallback)

        resp = claims_client.post("/api/v1/integration/connections", json=self.create_payload())

        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "IntegrationAuthenticationError"
        assert "details" in body and body["details"]["connection_id"] == "conn1"
        _, create_kwargs = mock_service.create_connection.call_args
        assert create_kwargs.get("replace_existing") is True
        _, sync_kwargs = mock_sync_orchestrator.sync_connection.call_args
        assert sync_kwargs.get("auth_token") is None
        assert sync_kwargs.get("public_fallback") is True

    def test_create_connection_without_login_endpoint_skips_login(
        self, claims_client, mock_service, mock_authenticator, override_deps_with_auth
    ):
        mock_service.create_connection = AsyncMock(return_value=connection_dto(name="Test API"))
        resp = claims_client.post(
            "/api/v1/integration/connections", json=self.create_payload(raw_spec=OPENAPI_V3_MINIMAL)
        )
        assert resp.status_code == 201
        mock_authenticator.login.assert_not_called()

    def test_sync_logs_in_and_passes_ephemeral_token(
        self, claims_client, mock_service, mock_sync_orchestrator, mock_authenticator, override_deps_with_auth
    ):
        result = SyncResult(connection_id="conn1", store_id=STORE_ID)
        result.status = "completed"
        result.completed_at = result.started_at
        mock_service.get_connection = AsyncMock(return_value=connection_dto(raw_spec=ECOMMERCE_SPEC))
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=result)

        resp = claims_client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 200
        mock_authenticator.login.assert_awaited_once()
        _, kwargs = mock_sync_orchestrator.sync_connection.call_args
        assert kwargs.get("auth_token") == "ecomm-token"

    def test_sync_login_failure_runs_public_fallback_with_401(
        self, claims_client, mock_service, mock_sync_orchestrator, mock_authenticator, override_deps_with_auth
    ):
        mock_service.get_connection = AsyncMock(return_value=connection_dto(raw_spec=ECOMMERCE_SPEC))
        mock_authenticator.login = AsyncMock(side_effect=IntegrationAuthenticationError())
        fallback = SyncResult(connection_id="conn1", store_id=STORE_ID)
        fallback.status = "completed"
        fallback.completed_at = fallback.started_at
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=fallback)

        resp = claims_client.post("/api/v1/integration/connections/conn1/sync", json={})

        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "IntegrationAuthenticationError"
        assert "sync" in body["details"]
        _, kwargs = mock_sync_orchestrator.sync_connection.call_args
        assert kwargs.get("auth_token") is None
        assert kwargs.get("public_fallback") is True

    def test_sync_without_claims_keeps_existing_flow(
        self, client, mock_service, mock_sync_orchestrator, mock_authenticator, override_deps_with_auth
    ):
        result = SyncResult(connection_id="conn1", store_id=STORE_ID)
        result.status = "completed"
        result.completed_at = result.started_at
        mock_service.get_connection = AsyncMock(return_value=connection_dto(raw_spec=ECOMMERCE_SPEC))
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=result)

        resp = client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 200
        mock_authenticator.login.assert_not_called()
        _, kwargs = mock_sync_orchestrator.sync_connection.call_args
        assert kwargs.get("auth_token") is None
