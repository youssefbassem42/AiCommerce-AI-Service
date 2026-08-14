"""PromoCodeService edge cases (Fix 5.5): platform integration failure modes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.recommendation.promo_service import PromoCodeService
from app.core.ai_settings import ai_settings
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType
from app.domain.integration.value_objects.entity_mapping import EntityMapping


def _connection(**overrides):
    defaults = {
        "id": "conn_1",
        "store_id": "s1",
        "organization_id": "o1",
        "name": "Shop API",
        "platform_name": "Shop",
        "status": ConnectionStatus.ACTIVE,
        "raw_spec": {"servers": [{"url": "https://api.shop.test"}]},
        "auth_config": AuthConfig(type=AuthType.BEARER, credentials_location="header", name="token", scheme="bearer"),
        "encrypted_credentials": "encrypted-blob",
        "entity_mappings": [EntityMapping(entity_type="coupon", id_field="id", list_path="/coupons")],
        "discovered_endpoints": [
            {"path": "/coupons", "method": "POST", "operation_id": "createCoupon", "summary": "Create coupon"}
        ],
        "discovered_schemas": {"POST /coupons": {"fields": [{"name": "code", "type": "string"}]}},
    }
    defaults.update(overrides)
    return IntegrationConnection(**defaults)


@pytest.fixture
def connection_repo():
    repo = AsyncMock()
    repo.find_many = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def promo_service(connection_repo):
    return PromoCodeService(connection_repo=connection_repo)


@pytest.fixture
def enable_promo_codes(monkeypatch):
    monkeypatch.setattr(ai_settings, "PROMO_CODES_ENABLED", True)


class TestPromoCodeEdgeCases:
    async def test_generate_with_empty_product_list(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [_connection()]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"code": "BUNDLE-X"})
        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", [], 10.0)
        assert code == "BUNDLE-X"

    async def test_generate_with_zero_discount(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [_connection()]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"code": "BUNDLE-ZERO"})
        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", ["p1"], 0.0)
        assert code == "BUNDLE-ZERO"

    async def test_generate_post_without_coupon_keyword_returns_none(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [
            _connection(discovered_endpoints=[{"path": "/widgets", "method": "POST", "operation_id": "createWidget"}])
        ]
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_unsafe_base_url_returns_none(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [
            _connection(raw_spec={"servers": [{"url": "http://169.254.169.254"}]})
        ]
        with patch.object(promo_service, "_build_client", side_effect=ValueError("unsafe base URL")):
            code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_schema_without_code_field_returns_none(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [
            _connection(discovered_schemas={"POST /coupons": {"fields": [{"name": "value", "type": "number"}]}})
        ]
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_fallback_canonical_payload_when_schema_unknown(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [_connection(discovered_schemas={})]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"id": "coupon_1"})
        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is not None
        kwargs = client.post.await_args.kwargs
        assert "code" in kwargs["body"]
        assert kwargs["body"]["value"] == 10.0

    async def test_redeem_analytics_failure_returns_false(self, promo_service, enable_promo_codes):
        with patch(
            "app.application.analytics.bundle_tracking_service.BundleTrackingService",
        ) as tracking_cls:
            tracking = AsyncMock()
            tracking.track_event = AsyncMock(side_effect=RuntimeError("mongo down"))
            tracking_cls.return_value = tracking
            result = await promo_service.redeem_code("BUNDLE-X", "s1")
        assert result is False

    async def test_inactive_connection_ignored(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [
            _connection(status=ConnectionStatus.INACTIVE, encrypted_credentials=None)
        ]
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None
        connection_repo.find_many.assert_awaited_once_with({"store_id": "s1", "status": "active"})
