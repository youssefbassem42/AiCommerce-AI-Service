from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_bundle_tracking_service
from app.core.auth_settings import auth_settings
from app.main import app
from app.middleware.audit import AuditMiddleware


def _admin_headers() -> dict[str, str]:
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "security_stamp": "test-security-stamp",
        "store_id": "22222222-2222-2222-2222-222222222222",
        "org_id": "33333333-3333-3333-3333-333333333333",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": "Admin",
        "iss": auth_settings.JWT_ISSUER,
        "aud": auth_settings.JWT_AUDIENCE,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    token = pyjwt.encode(payload, auth_settings.JWT_SECRET, algorithm=auth_settings.JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(app, raise_server_exceptions=False, headers=_admin_headers())


@pytest.fixture
def mock_tracking_service():
    svc = MagicMock()
    svc.track_copy_event = AsyncMock(
        return_value={
            "bundle_key": "abc123",
            "copy_count": 3,
            "is_top": False,
            "threshold": 5,
        }
    )
    svc.get_tracked_bundles = AsyncMock()
    svc.get_tracked_bundle = AsyncMock()
    svc.promote_bundle = AsyncMock()
    svc.demote_bundle = AsyncMock()
    svc.get_config = AsyncMock()
    svc.update_config = AsyncMock()
    return svc


def _clear_overrides():
    app.dependency_overrides.clear()


class TestAdminBundleAPI:
    def test_track_copy_event_endpoint_exists(self, client, mock_tracking_service):
        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/track",
                json={
                    "store_id": "store_1",
                    "promo_code": "BUNDLE-TEST",
                    "product_ids": ["p1", "p2"],
                    "discount_pct": 10.0,
                    "total_discount": 50.0,
                    "total_original": 500.0,
                },
            )
            assert response.status_code == 200
        finally:
            _clear_overrides()

    def test_track_copy_event_validation_error(self, client):
        response = client.post(
            "/api/v1/admin/bundles/track",
            json={"store_id": "store_1"},
        )
        assert response.status_code == 422

    def test_track_copy_event_success(self, client, mock_tracking_service):
        mock_tracking_service.track_copy_event.return_value = {
            "bundle_key": "abc123",
            "copy_count": 3,
            "is_top": False,
            "threshold": 5,
        }

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/track",
                json={
                    "store_id": "store_1",
                    "promo_code": "BUNDLE-TEST",
                    "product_ids": ["p1", "p2"],
                    "discount_pct": 10.0,
                    "total_discount": 50.0,
                    "total_original": 500.0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["bundle_key"] == "abc123"
            assert data["copy_count"] == 3
            assert data["is_top"] is False
        finally:
            _clear_overrides()

    def test_track_copy_event_promotes(self, client, mock_tracking_service):
        mock_tracking_service.track_copy_event.return_value = {
            "bundle_key": "abc123",
            "copy_count": 5,
            "is_top": True,
            "threshold": 5,
        }

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/track",
                json={
                    "store_id": "store_1",
                    "promo_code": "BUNDLE-TEST",
                    "product_ids": ["p1", "p2"],
                    "discount_pct": 10.0,
                    "total_discount": 50.0,
                    "total_original": 500.0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["is_top"] is True
            assert data["copy_count"] == 5
        finally:
            _clear_overrides()

    def test_track_copy_event_service_error(self, client, mock_tracking_service):
        mock_tracking_service.track_copy_event.side_effect = Exception("DB failure")

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/track",
                json={
                    "store_id": "store_1",
                    "promo_code": "BUNDLE-TEST",
                    "product_ids": ["p1"],
                    "discount_pct": 10.0,
                    "total_discount": 10.0,
                    "total_original": 100.0,
                },
            )
            assert response.status_code == 500
        finally:
            _clear_overrides()

    def test_list_tracked_bundles(self, client, mock_tracking_service):
        mock_tracking_service.get_tracked_bundles.return_value = [
            {
                "id": "doc1",
                "store_id": "store_1",
                "bundle_key": "key1",
                "product_ids": ["p1", "p2"],
                "discount_pct": 10.0,
                "total_original": 500.0,
                "total_discount": 50.0,
                "promo_code": "B1",
                "copy_count": 5,
                "is_top": True,
                "promoted_at": "2026-07-25T00:00:00",
                "first_copied_at": "2026-07-20T00:00:00",
                "last_copied_at": "2026-07-25T00:00:00",
            },
        ]

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.get("/api/v1/admin/bundles/tracking?store_id=store_1")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["bundle_key"] == "key1"
            assert data[0]["copy_count"] == 5
        finally:
            _clear_overrides()

    def test_list_tracked_bundles_top_only(self, client, mock_tracking_service):
        mock_tracking_service.get_tracked_bundles.return_value = []

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.get("/api/v1/admin/bundles/tracking?top_only=true")
            assert response.status_code == 200
            mock_tracking_service.get_tracked_bundles.assert_called_once_with(
                "22222222-2222-2222-2222-222222222222", is_top_only=True
            )
        finally:
            _clear_overrides()

    def test_get_single_tracked_bundle(self, client, mock_tracking_service):
        mock_tracking_service.get_tracked_bundle.return_value = {
            "id": "doc1",
            "store_id": "store_1",
            "bundle_key": "key1",
            "product_ids": ["p1"],
            "discount_pct": 5.0,
            "total_original": 200.0,
            "total_discount": 10.0,
            "promo_code": "B1",
            "copy_count": 3,
            "is_top": False,
        }

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.get("/api/v1/admin/bundles/tracking/key1?store_id=store_1")
            assert response.status_code == 200
            data = response.json()
            assert data["bundle_key"] == "key1"
            assert data["copy_count"] == 3
        finally:
            _clear_overrides()

    def test_get_single_tracked_bundle_not_found(self, client, mock_tracking_service):
        mock_tracking_service.get_tracked_bundle.return_value = None

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.get("/api/v1/admin/bundles/tracking/nonexistent?store_id=store_1")
            assert response.status_code == 404
        finally:
            _clear_overrides()

    def test_promote_bundle(self, client, mock_tracking_service):
        mock_tracking_service.promote_bundle.return_value = True

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/top/promote?store_id=store_1",
                json={"bundle_key": "key1"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "promoted"
        finally:
            _clear_overrides()

    def test_promote_bundle_not_found(self, client, mock_tracking_service):
        mock_tracking_service.promote_bundle.return_value = False

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.post(
                "/api/v1/admin/bundles/top/promote?store_id=store_1",
                json={"bundle_key": "nonexistent"},
            )
            assert response.status_code == 404
        finally:
            _clear_overrides()

    def test_demote_bundle(self, client, mock_tracking_service):
        mock_tracking_service.demote_bundle.return_value = True

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.delete(
                "/api/v1/admin/bundles/top/key1?store_id=store_1",
            )
            assert response.status_code == 200
            assert response.json()["status"] == "demoted"
        finally:
            _clear_overrides()

    def test_demote_bundle_not_found(self, client, mock_tracking_service):
        mock_tracking_service.demote_bundle.return_value = False

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.delete(
                "/api/v1/admin/bundles/top/nonexistent?store_id=store_1",
            )
            assert response.status_code == 404
        finally:
            _clear_overrides()

    def test_get_config(self, client, mock_tracking_service):
        mock_tracking_service.get_config.return_value = {
            "threshold": 3,
            "enabled": True,
        }

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.get("/api/v1/admin/bundles/config?store_id=store_1")
            assert response.status_code == 200
            data = response.json()
            assert data["threshold"] == 3
        finally:
            _clear_overrides()

    def test_update_config(self, client, mock_tracking_service):
        mock_tracking_service.update_config.return_value = {
            "threshold": 10,
            "enabled": True,
        }

        app.dependency_overrides[get_bundle_tracking_service] = lambda: mock_tracking_service
        try:
            response = client.put(
                "/api/v1/admin/bundles/config?store_id=store_1",
                json={"threshold": 10},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["threshold"] == 10
        finally:
            _clear_overrides()

    def test_update_config_validation_error(self, client):
        response = client.put(
            "/api/v1/admin/bundles/config?store_id=store_1",
            json={"threshold": 0},
        )
        assert response.status_code == 422
