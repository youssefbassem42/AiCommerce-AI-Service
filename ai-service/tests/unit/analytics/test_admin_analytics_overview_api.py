from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.admin.dependencies import get_sentiment_analytics_service
from app.api.auth.dependencies import require_super_admin_role
from app.main import app


@pytest.fixture(autouse=True)
def _bypass_auth():
    app.dependency_overrides[require_super_admin_role] = lambda: None
    yield
    app.dependency_overrides.pop(require_super_admin_role, None)


def _mock_service(**kwargs):
    svc = AsyncMock()
    svc.get_sentiment_overview.return_value = {
        "total": kwargs.get("total", 0),
        "positive_count": kwargs.get("positive_count", 0),
        "neutral_count": kwargs.get("neutral_count", 0),
        "negative_count": kwargs.get("negative_count", 0),
        "positive_pct": kwargs.get("positive_pct", 0.0),
        "neutral_pct": kwargs.get("neutral_pct", 0.0),
        "negative_pct": kwargs.get("negative_pct", 0.0),
    }
    return svc


class TestAdminSentimentOverviewAPI:
    def test_returns_overview_breakdown(self):
        svc = _mock_service(
            total=100,
            positive_count=50,
            neutral_count=30,
            negative_count=20,
            positive_pct=50.0,
            neutral_pct=30.0,
            negative_pct=20.0,
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["positive_count"] == 50
        assert data["neutral_count"] == 30
        assert data["negative_count"] == 20
        assert data["positive_pct"] == 50.0
        assert data["neutral_pct"] == 30.0
        assert data["negative_pct"] == 20.0

    def test_no_tickets_returns_zeros(self):
        svc = _mock_service()
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["positive_count"] == 0
        assert data["neutral_count"] == 0
        assert data["negative_count"] == 0
        assert data["positive_pct"] == 0.0
        assert data["neutral_pct"] == 0.0
        assert data["negative_pct"] == 0.0

    def test_service_error_returns_500(self):
        svc = AsyncMock()
        svc.get_sentiment_overview.side_effect = Exception("DB error")
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 500
        assert "DB error" in response.text

    def test_all_positive(self):
        svc = _mock_service(total=5, positive_count=5, positive_pct=100.0)
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["positive_pct"] == 100.0
        assert data["neutral_pct"] == 0.0
        assert data["negative_pct"] == 0.0

    def test_negative_only(self):
        svc = _mock_service(total=3, negative_count=3, negative_pct=100.0)
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["negative_pct"] == 100.0
        assert data["positive_pct"] == 0.0
        assert data["neutral_pct"] == 0.0

    def test_rounds_correctly(self):
        svc = _mock_service(
            total=3,
            positive_count=1,
            neutral_count=1,
            negative_count=1,
            positive_pct=33.3,
            neutral_pct=33.3,
            negative_pct=33.3,
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["positive_pct"] == 33.3
        assert data["neutral_pct"] == 33.3
        assert data["negative_pct"] == 33.3
