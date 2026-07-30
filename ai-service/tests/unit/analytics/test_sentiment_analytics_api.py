from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.analytics.dependencies import get_sentiment_analytics_service, require_admin_role
from app.api.analytics.schemas import SentimentSummaryResponse
from app.main import app


@pytest.fixture(autouse=True)
def _bypass_auth():
    app.dependency_overrides[require_admin_role] = lambda: None
    yield
    app.dependency_overrides.clear()


def _mock_service(store_id: str = "s1", **kwargs):
    svc = AsyncMock()
    svc.get_sentiment_summary.return_value = SentimentSummaryResponse(
        store_id=store_id,
        total=kwargs.get("total", 0),
        positive_count=kwargs.get("positive_count", 0),
        neutral_count=kwargs.get("neutral_count", 0),
        negative_count=kwargs.get("negative_count", 0),
        positive_pct=kwargs.get("positive_pct", 0.0),
        neutral_pct=kwargs.get("neutral_pct", 0.0),
        negative_pct=kwargs.get("negative_pct", 0.0),
    )
    return svc


class TestSentimentAnalyticsAPI:
    def test_returns_sentiment_breakdown(self):
        svc = _mock_service(
            store_id="s1",
            total=10,
            positive_count=4,
            neutral_count=4,
            negative_count=2,
            positive_pct=40.0,
            neutral_pct=40.0,
            negative_pct=20.0,
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s1")

        assert response.status_code == 200
        data = response.json()
        assert data["store_id"] == "s1"
        assert data["total"] == 10
        assert data["positive_count"] == 4
        assert data["neutral_count"] == 4
        assert data["negative_count"] == 2
        assert data["positive_pct"] == 40.0
        assert data["neutral_pct"] == 40.0
        assert data["negative_pct"] == 20.0

    def test_no_tickets_returns_zeros(self):
        svc = _mock_service(store_id="s2")
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["positive_count"] == 0
        assert data["neutral_count"] == 0
        assert data["negative_count"] == 0

    def test_missing_store_id_returns_422(self):
        client = TestClient(app)
        response = client.get("/api/v1/analytics/sentiment-summary")
        assert response.status_code == 422

    def test_service_error_returns_500(self):
        svc = AsyncMock()
        svc.get_sentiment_summary.side_effect = Exception("DB error")
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s1")

        assert response.status_code == 500
        assert "DB error" in response.text

    def test_all_positive(self):
        svc = _mock_service(
            store_id="s1", total=5, positive_count=5, positive_pct=100.0
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s1")

        assert response.status_code == 200
        data = response.json()
        assert data["positive_pct"] == 100.0
        assert data["neutral_pct"] == 0.0
        assert data["negative_pct"] == 0.0

    def test_negative_only(self):
        svc = _mock_service(
            store_id="s3", total=3, negative_count=3, negative_pct=100.0
        )
        app.dependency_overrides[get_sentiment_analytics_service] = lambda: svc
        client = TestClient(app)

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s3")

        assert response.status_code == 200
        data = response.json()
        assert data["negative_pct"] == 100.0
        assert data["positive_pct"] == 0.0
        assert data["neutral_pct"] == 0.0

    def test_rounds_correctly(self):
        svc = _mock_service(
            store_id="s1",
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

        response = client.get("/api/v1/analytics/sentiment-summary?store_id=s1")

        assert response.status_code == 200
        data = response.json()
        assert data["positive_pct"] == 33.3
        assert data["neutral_pct"] == 33.3
