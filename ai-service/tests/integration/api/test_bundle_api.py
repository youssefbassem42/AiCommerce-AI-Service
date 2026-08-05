from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.recommendation.dependencies import get_bundle_service
from app.application.recommendation.dto.recommendation_dto import (
    BundleCandidate,
    BundleResponse,
    DiscountInfo,
)
from app.main import app
from app.middleware.audit import AuditMiddleware


@pytest.fixture
def client():
    with patch.object(AuditMiddleware, "_log_audit_entry", AsyncMock()):
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_bundle_service():
    service = MagicMock()
    service.suggest = AsyncMock()
    return service


def _clear_overrides():
    app.dependency_overrides.clear()


class TestBundleAPI:
    def test_bundle_suggestion_endpoint_exists(self, client, mock_bundle_service):
        mock_bundle_service.suggest.return_value = BundleResponse(
            query="I have $300 and want a monitor",
            store_id="store_1",
            budget=300.0,
            bundles=[],
        )

        app.dependency_overrides[get_bundle_service] = lambda: mock_bundle_service
        try:
            response = client.post(
                "/api/v1/recommendations/bundle-suggestion",
                json={
                    "message": "I have $300 and want a monitor",
                    "store_id": "store_1",
                },
            )
            assert response.status_code == 200
        finally:
            _clear_overrides()

    def test_bundle_suggestion_validation_error(self, client):
        response = client.post(
            "/api/v1/recommendations/bundle-suggestion",
            json={"store_id": "store_1"},
        )
        assert response.status_code == 422

    def test_bundle_suggestion_returns_bundles(self, client, mock_bundle_service):
        mock_bundle_service.suggest.return_value = BundleResponse(
            query="I have $300 and want a monitor",
            store_id="store_1",
            customer_id="cust_1",
            budget=300.0,
            bundles=[
                BundleCandidate(
                    products=[
                        DiscountInfo(
                            product_id="p1",
                            product_title="Monitor 24in",
                            original_price=Decimal("250"),
                            discount_pct=10.0,
                            discount_amount=Decimal("25"),
                            price_after_discount=Decimal("225"),
                        ),
                    ],
                    total_original=Decimal("250"),
                    total_discount=Decimal("25"),
                    total_after_discount=Decimal("225"),
                    remaining_budget=75.0,
                    within_budget=True,
                    promo_code="BUNDLE-TEST123",
                    rank=1,
                ),
            ],
            promo_code="BUNDLE-TEST123",
            rationale="Best bundle for your budget",
        )

        app.dependency_overrides[get_bundle_service] = lambda: mock_bundle_service
        try:
            response = client.post(
                "/api/v1/recommendations/bundle-suggestion",
                json={
                    "message": "I have $300 and want a monitor",
                    "store_id": "store_1",
                    "customer_id": "cust_1",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["budget"] == 300.0
            assert len(data["bundles"]) == 1
            assert data["promo_code"] == "BUNDLE-TEST123"
            assert data["bundles"][0]["total_original"] == "250"
        finally:
            _clear_overrides()

    def test_bundle_suggestion_empty_results(self, client, mock_bundle_service):
        mock_bundle_service.suggest.return_value = BundleResponse(
            query="I have $10",
            store_id="store_1",
            budget=10.0,
            bundles=[],
            rationale="No bundles within budget",
        )

        app.dependency_overrides[get_bundle_service] = lambda: mock_bundle_service
        try:
            response = client.post(
                "/api/v1/recommendations/bundle-suggestion",
                json={
                    "message": "I have $10",
                    "store_id": "store_1",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["budget"] == 10.0
            assert data["bundles"] == []
        finally:
            _clear_overrides()

    def test_bundle_suggestion_service_error(self, client, mock_bundle_service):
        mock_bundle_service.suggest.side_effect = Exception("Service failure")

        app.dependency_overrides[get_bundle_service] = lambda: mock_bundle_service
        try:
            response = client.post(
                "/api/v1/recommendations/bundle-suggestion",
                json={
                    "message": "test",
                    "store_id": "store_1",
                },
            )
            assert response.status_code == 500
        finally:
            _clear_overrides()
