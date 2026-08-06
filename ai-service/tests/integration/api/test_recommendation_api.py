from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.recommendation.dependencies import get_recommendation_service
from app.application.recommendation.dto.recommendation_dto import (
    ProductCard,
    RecommendationResponse,
)
from app.main import app
from app.middleware.audit import AuditMiddleware
from tests.conftest import admin_headers


@pytest.fixture
def client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(app, raise_server_exceptions=False, headers=admin_headers())


@pytest.fixture
def mock_service():
    service = MagicMock()
    service.recommend = AsyncMock()
    return service


def _clear_overrides():
    app.dependency_overrides.clear()


class TestRecommendationAPI:
    def test_recommend_chat_endpoint_exists(self, client):
        response = client.post(
            "/api/v1/recommendations/chat",
            json={
                "message": "gaming laptop",
                "store_id": "store_1",
            },
        )
        assert response.status_code in (200, 422, 500)

    def test_recommend_chat_validation_error(self, client):
        response = client.post(
            "/api/v1/recommendations/chat",
            json={"store_id": "store_1"},
        )
        assert response.status_code == 422

    def test_recommend_chat_returns_products(self, client, mock_service):
        mock_service.recommend.return_value = RecommendationResponse(
            query="gaming laptop",
            store_id="store_1",
            customer_id="cust_1",
            products=[
                ProductCard(
                    product_id="p1",
                    title="Gaming Laptop Pro",
                    price=Decimal("1299.99"),
                    match_reasons=["High performance GPU"],
                ),
            ],
            rationale="Best match for gaming",
            total_count=1,
            latency_ms=100.0,
        )

        app.dependency_overrides[get_recommendation_service] = lambda: mock_service
        try:
            response = client.post(
                "/api/v1/recommendations/chat",
                json={
                    "message": "gaming laptop",
                    "store_id": "store_1",
                    "customer_id": "cust_1",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "gaming laptop"
            assert data["store_id"] == "store_1"
            assert data["total_count"] == 1
            assert len(data["products"]) == 1
            assert data["products"][0]["product_id"] == "p1"
            assert data["products"][0]["title"] == "Gaming Laptop Pro"
        finally:
            _clear_overrides()

    def test_recommend_chat_empty_results(self, client, mock_service):
        mock_service.recommend.return_value = RecommendationResponse(
            query="unknown item xyz",
            store_id="store_1",
            products=[],
            rationale="No products found",
            total_count=0,
            latency_ms=50.0,
        )

        app.dependency_overrides[get_recommendation_service] = lambda: mock_service
        try:
            response = client.post(
                "/api/v1/recommendations/chat",
                json={
                    "message": "unknown item xyz",
                    "store_id": "store_1",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 0
            assert data["products"] == []
        finally:
            _clear_overrides()

    def test_recommend_chat_service_error(self, client, mock_service):
        mock_service.recommend.side_effect = Exception("Service failure")

        app.dependency_overrides[get_recommendation_service] = lambda: mock_service
        try:
            response = client.post(
                "/api/v1/recommendations/chat",
                json={
                    "message": "test",
                    "store_id": "store_1",
                },
            )
            assert response.status_code == 500
        finally:
            _clear_overrides()
