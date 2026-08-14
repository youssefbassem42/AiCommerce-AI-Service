"""Widget bundle funnel analytics endpoint (Fix 5.6): /api/v1/widget/bundles/events."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.application.widget.token_service import widget_token_service
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _widget_token(scopes=None):
    token, _ = widget_token_service.create_session_token(
        widget_id="widget-1",
        store_id="store-1",
        organization_id="org-1",
        scopes=scopes or ["recommendations:read"],
    )
    return token


def _headers(scopes=None):
    return {"Authorization": f"Bearer {_widget_token(scopes)}"}


def test_bundle_clicked_recorded(client):
    tracker = MagicMock()
    tracker.track_event = AsyncMock(return_value={"recorded": True})

    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        response = client.post(
            "/api/v1/widget/bundles/events",
            json={
                "event": "bundle_clicked",
                "bundle_key": "bundle-1",
                "product_ids": ["p1", "p2"],
                "discount_pct": 15.0,
                "conversation_id": "conv-1",
                "customer_id": "customer-1",
            },
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"event": "bundle_clicked", "recorded": True}
    tracker.track_event.assert_awaited_once()
    kwargs = tracker.track_event.await_args.kwargs
    assert kwargs["store_id"] == "store-1"
    assert kwargs["event"] == "bundle_clicked"
    assert kwargs["bundle_key"] == "bundle-1"
    assert kwargs["product_ids"] == ["p1", "p2"]
    assert kwargs["discount_pct"] == 15.0
    assert kwargs["conversation_id"] == "conv-1"
    assert kwargs["customer_id"] == "customer-1"


def test_promo_copied_recorded(client):
    tracker = MagicMock()
    tracker.track_event = AsyncMock(return_value={"recorded": True})

    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        response = client.post(
            "/api/v1/widget/bundles/events",
            json={"event": "promo_copied", "promo_code": "BUNDLE-X"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"event": "promo_copied", "recorded": True}
    assert tracker.track_event.await_args.kwargs["promo_code"] == "BUNDLE-X"


def test_promo_applied_recorded(client):
    tracker = MagicMock()
    tracker.track_event = AsyncMock(return_value={"recorded": True})

    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        response = client.post(
            "/api/v1/widget/bundles/events",
            json={"event": "promo_applied", "promo_code": "BUNDLE-X"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"event": "promo_applied", "recorded": True}


def test_analytics_failure_still_returns_200(client):
    tracker = MagicMock()
    tracker.track_event = AsyncMock(side_effect=RuntimeError("db down"))

    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        response = client.post(
            "/api/v1/widget/bundles/events",
            json={"event": "bundle_clicked"},
            headers=_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"event": "bundle_clicked", "recorded": False}


def test_missing_scope_forbidden(client):
    response = client.post(
        "/api/v1/widget/bundles/events",
        json={"event": "bundle_clicked"},
        headers=_headers(scopes=["rag:chat"]),
    )
    assert response.status_code == 403


def test_anonymous_unauthorized(client):
    response = client.post(
        "/api/v1/widget/bundles/events",
        json={"event": "bundle_clicked"},
    )
    assert response.status_code == 401


def test_invalid_event_rejected(client):
    response = client.post(
        "/api/v1/widget/bundles/events",
        json={"event": "unknown_event"},
        headers=_headers(),
    )
    assert response.status_code == 422
