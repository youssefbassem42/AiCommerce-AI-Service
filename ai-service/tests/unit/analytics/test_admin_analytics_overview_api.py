from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_sentiment_analytics_service
from app.api.auth.dependencies import require_super_admin_role
from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.get_sentiment_overview = AsyncMock(
        return_value={
            "total": 10,
            "positive_count": 5,
            "neutral_count": 3,
            "negative_count": 2,
            "positive_pct": 50.0,
            "neutral_pct": 30.0,
            "negative_pct": 20.0,
        }
    )
    return service


@pytest.fixture
def override_deps(client, mock_service):
    app.dependency_overrides[get_sentiment_analytics_service] = lambda: mock_service
    app.dependency_overrides[require_super_admin_role] = lambda: None
    yield
    app.dependency_overrides.pop(get_sentiment_analytics_service, None)
    app.dependency_overrides.pop(require_super_admin_role, None)


class TestAdminAnalyticsOverviewApi:
    def test_overview_returns_counts(self, client, override_deps):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert data["positive_count"] == 5
        assert data["neutral_count"] == 3
        assert data["negative_count"] == 2

    def test_overview_returns_percentages(self, client, override_deps):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["positive_pct"] == 50.0
        assert data["neutral_pct"] == 30.0
        assert data["negative_pct"] == 20.0

    def test_overview_zero_totals(self, client, mock_service, override_deps):
        mock_service.get_sentiment_overview.return_value = {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
        }

        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["positive_pct"] == 0.0

    def test_overview_requires_super_admin(self, client, mock_service):
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: mock_service
        try:
            resp = client.get("/api/v1/admin/analytics/sentiment/overview")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_sentiment_analytics_service, None)

    def test_overview_returns_500_on_service_failure(self, client, mock_service, override_deps):
        mock_service.get_sentiment_overview.side_effect = RuntimeError("db down")

        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 500

    def test_overview_response_schema_fields(self, client, override_deps):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        assert set(resp.json().keys()) == {
            "total",
            "positive_count",
            "neutral_count",
            "negative_count",
            "positive_pct",
            "neutral_pct",
            "negative_pct",
        }
