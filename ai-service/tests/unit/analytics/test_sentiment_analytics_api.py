import pytest
from fastapi.testclient import TestClient

from app.api.auth.dependencies import require_super_admin_role
from app.main import app


class FakeCursor:
    def __init__(self, results):
        self._results = results

    async def to_list(self, length):
        return self._results[:length] if length else self._results


class FakeCollection:
    def __init__(self, results):
        self._results = results

    def aggregate(self, pipeline):
        return FakeCursor(self._results)


@pytest.fixture
def collection(monkeypatch):
    fake = FakeCollection([])
    monkeypatch.setattr(
        "app.application.analytics.sentiment_analytics_service.get_ticket_analysis_collection",
        lambda: fake,
    )
    return fake


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def admin_override():
    app.dependency_overrides[require_super_admin_role] = lambda: None
    yield
    app.dependency_overrides.pop(require_super_admin_role, None)


class TestSentimentAnalyticsApi:
    def test_overview_empty_collection(self, client, collection, admin_override):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        assert resp.json() == {
            "total": 0,
            "positive_count": 0,
            "neutral_count": 0,
            "negative_count": 0,
            "positive_pct": 0.0,
            "neutral_pct": 0.0,
            "negative_pct": 0.0,
        }

    def test_overview_with_data(self, client, collection, admin_override):
        collection._results = [
            {
                "total": 10,
                "positive_count": 6,
                "neutral_count": 3,
                "negative_count": 1,
            }
        ]

        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 200
        data = resp.json()
        assert data["positive_pct"] == 60.0
        assert data["neutral_pct"] == 30.0
        assert data["negative_pct"] == 10.0

    def test_overview_aggregate_failure_returns_500(self, client, collection, admin_override):
        def boom(pipeline):
            raise RuntimeError("aggregate failed")

        collection.aggregate = boom

        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 500

    def test_overview_requires_super_admin_role(self, client, collection):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")

        assert resp.status_code == 401

    def test_overview_only_registers_expected_overrides(self, client, collection, admin_override):
        resp = client.get("/api/v1/admin/analytics/sentiment/overview")
        assert resp.status_code == 200
        assert set(app.dependency_overrides.keys()) == {require_super_admin_role}

    def test_overview_rejects_non_get_methods(self, client, admin_override):
        resp = client.post("/api/v1/admin/analytics/sentiment/overview", json={})

        assert resp.status_code == 405
