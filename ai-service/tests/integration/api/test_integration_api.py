import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.api.integration.dependencies import get_integration_service, get_sync_orchestrator
from app.application.integration.sync.orchestrator import SyncOrchestrator, SyncResult
from app.main import app

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


@pytest.fixture
def client():
    return TestClient(app)


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
def override_deps(client, mock_service, mock_sync_orchestrator):
    app.dependency_overrides[get_integration_service] = lambda: mock_service
    app.dependency_overrides[get_sync_orchestrator] = lambda: mock_sync_orchestrator
    yield
    app.dependency_overrides.clear()


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
        resp = client.post("/api/v1/integration/schemas/parse", json={
            "platform_name": "shopify",
            "raw_spec": OPENAPI_V3_MINIMAL,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["platform_name"] == "shopify"
        assert data["base_url"] == "https://api.test.com"

    def test_parse_spec_invalid(self, client, mock_service, override_deps):
        from app.domain.integration.exceptions import InvalidSpecException
        mock_service.parse_spec.side_effect = InvalidSpecException("Invalid spec")
        resp = client.post("/api/v1/integration/schemas/parse", json={
            "platform_name": "shopify",
            "raw_spec": {"invalid": True},
        })
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
                    "auth_config": {"type": "apiKey", "credentials_location": "header", "scheme": None, "name": "X-API-Key", "token_url": None, "flow": None},
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
        resp = client.post("/api/v1/integration/connections", json={
            "store_id": "s1",
            "name": "Test Connection",
            "platform_name": "shopify",
            "raw_spec": OPENAPI_V3_MINIMAL,
            "auth_config": {"type": "apiKey", "name": "X-API-Key"},
        })
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
        mock_service.get_connection = AsyncMock(return_value=MagicMock(
            model_dump=MagicMock(
                return_value={
                    "id": "conn1",
                    "store_id": "s1",
                    "organization_id": "o1",
                    "name": "Test",
                    "platform_name": "shopify",
                    "status": "active",
                    "spec_version": "3.0",
                    "auth_config": {"type": "apiKey", "credentials_location": "header", "scheme": None, "name": "X-API-Key", "token_url": None, "flow": None},
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
        ))
        resp = client.get("/api/v1/integration/connections/conn1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "conn1"

    def test_sync_connection(self, client, mock_sync_orchestrator, override_deps):
        result = SyncResult(connection_id="conn1", store_id="s1")
        result.status = "completed"
        result.completed_at = result.started_at
        mock_sync_orchestrator.sync_connection = AsyncMock(return_value=result)

        resp = client.post("/api/v1/integration/connections/conn1/sync", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["connection_id"] == "conn1"
        assert data["status"] == "completed"
        assert "started_at" in data

    def test_sync_connection_not_found(self, client, mock_sync_orchestrator, override_deps):
        mock_sync_orchestrator.sync_connection = AsyncMock(side_effect=ValueError("not found"))
        resp = client.post("/api/v1/integration/connections/nonexistent/sync", json={})
        assert resp.status_code == 500

    def test_update_mappings(self, client, mock_service, override_deps):
        mock_service.update_mappings = AsyncMock(return_value=MagicMock(
            model_dump=MagicMock(
                return_value={
                    "id": "conn1",
                    "store_id": "s1",
                    "organization_id": "o1",
                    "name": "Test",
                    "platform_name": "shopify",
                    "status": "active",
                    "spec_version": "3.0",
                    "auth_config": {"type": "apiKey", "credentials_location": "header", "scheme": None, "name": "X-API-Key", "token_url": None, "flow": None},
                    "entity_mappings": [{"entity_type": "product", "list_path": "/products.json", "list_method": "GET", "detail_path": None, "detail_method": "GET", "id_field": "id", "pagination": {"style": "none", "page_param": None, "limit_param": None, "default_limit": 20, "cursor_field": None, "total_field": None, "next_link_field": None}, "field_mappings": []}],
                    "discovered_endpoints": [],
                    "discovered_schemas": {},
                    "last_sync_at": None,
                    "last_sync_status": None,
                    "error_message": None,
                    "created_at": "2026-01-01T00:00:00",
                    "updated_at": "2026-01-01T00:00:00",
                }
            )
        ))
        resp = client.put("/api/v1/integration/connections/conn1/mappings", json={
            "entity_mappings": [{
                "entity_type": "product",
                "list_path": "/products.json",
                "id_field": "id",
                "field_mappings": [],
            }],
        })
        assert resp.status_code == 200

    def test_delete_connection(self, client, mock_service, override_deps):
        mock_service.delete_connection = AsyncMock(return_value=True)
        resp = client.delete("/api/v1/integration/connections/conn1")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
