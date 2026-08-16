"""PromoCodeService (Fix 5.5): real coupons on the e-commerce platform only."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.recommendation.promo_service import PROMO_CODE_PREFIX, PromoCodeService
from app.core.ai_settings import ai_settings
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType
from app.domain.integration.value_objects.entity_mapping import EntityMapping


def _connection(store_id: str = "s1", entity_types: list[str] | None = None, endpoints: list[dict] | None = None):
    entity_types = entity_types or ["product", "coupon"]
    return IntegrationConnection(
        id="conn_1",
        store_id=store_id,
        organization_id="o1",
        name="Shop API",
        platform_name="Shop",
        status=ConnectionStatus.ACTIVE,
        raw_spec={
            "servers": [{"url": "https://api.shop.test"}],
            "paths": {
                "/coupons": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"code": {}, "percentage": {}}}
                                }
                            }
                        }
                    }
                }
            },
        },
        auth_config=AuthConfig(type=AuthType.BEARER, credentials_location="header", name="token", scheme="bearer"),
        encrypted_credentials="encrypted-blob",
        entity_mappings=[
            EntityMapping(entity_type=et, id_field="id", list_path=f"/{et}s" if et != "coupon" else "/coupons")
            for et in entity_types
        ],
        discovered_endpoints=endpoints
        or [
            {"path": "/coupons", "method": "POST", "operation_id": "createCoupon", "summary": "Create coupon"},
            {"path": "/products", "method": "GET", "operation_id": "listProducts", "summary": "List products"},
        ],
        discovered_schemas={
            "POST /coupons": {"fields": [{"name": "code", "type": "string"}, {"name": "percentage", "type": "number"}]}
        },
    )


@pytest.fixture
def connection_repo():
    repo = AsyncMock()
    repo.find_many = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def promo_service(connection_repo):
    service = PromoCodeService(connection_repo=connection_repo)
    return service


@pytest.fixture
def enable_promo_codes(monkeypatch):
    monkeypatch.setattr(ai_settings, "PROMO_CODES_ENABLED", True)


@pytest.fixture
def disable_promo_codes(monkeypatch):
    monkeypatch.setattr(ai_settings, "PROMO_CODES_ENABLED", False)


class TestPromoCodeService:
    async def test_generate_disabled_by_config_returns_none(
        self, promo_service, connection_repo, disable_promo_codes
    ):
        assert ai_settings.PROMO_CODES_ENABLED is False
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None
        connection_repo.find_many.assert_not_awaited()

    async def test_generate_no_connection_returns_none(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = []
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_connection_without_coupons_returns_none(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [_connection(entity_types=["product"])]
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_connection_without_create_endpoint_returns_none(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [
            _connection(endpoints=[{"path": "/coupons", "method": "GET", "operation_id": "listCoupons"}])
        ]
        code = await promo_service.generate_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_creates_real_coupon(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [_connection()]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"code": "BUNDLE-PLATFORM1", "id": "coupon_1"})

        with (
            patch.object(promo_service, "_build_client", return_value=client),
            patch.object(promo_service._key_manager, "decrypt_secret", return_value='{"token": "abc"}'),
        ):
            code = await promo_service.generate_code("s1", ["p1", "p2"], 10.0)

        assert code == "BUNDLE-PLATFORM1"
        client.post.assert_awaited_once()
        assert client.post.await_args.args[0] == "/coupons"
        kwargs = client.post.await_args.kwargs
        assert kwargs["body"]["code"].startswith(f"{PROMO_CODE_PREFIX}-")
        assert kwargs["body"]["percentage"] == 10.0

    async def test_generate_uses_generated_code_when_response_has_none(
        self, promo_service, connection_repo, enable_promo_codes
    ):
        connection_repo.find_many.return_value = [_connection()]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"id": "coupon_1"})

        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", ["p1"], 5.0)

        assert code is not None
        assert code.startswith(f"{PROMO_CODE_PREFIX}-")

    async def test_generate_platform_failure_returns_none(self, promo_service, connection_repo, enable_promo_codes):
        connection_repo.find_many.return_value = [_connection()]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(side_effect=RuntimeError("platform down"))

        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", ["p1"], 10.0)

        assert code is None

    async def test_generate_uses_path_keyword_fallback(self, promo_service, connection_repo, enable_promo_codes):
        conn = _connection(entity_types=["promotion"])
        conn = conn.model_copy(
            deep=True,
            update={
                "discovered_endpoints": [{"path": "/promotions", "method": "POST", "operation_id": "createPromotion"}],
                "discovered_schemas": {},
            },
        )
        connection_repo.find_many.return_value = [conn]
        client = MagicMock()
        client.close = AsyncMock()
        client.post = AsyncMock(return_value={"coupon_code": "PROMO-X1"})

        with patch.object(promo_service, "_build_client", return_value=client):
            code = await promo_service.generate_code("s1", ["p1"], 10.0)

        assert code == "PROMO-X1"
        assert client.post.await_args.args[0] == "/promotions"
        kwargs = client.post.await_args.kwargs
        assert "code" in kwargs["body"]

    async def test_redeem_code_records_analytics(self, promo_service, enable_promo_codes):
        with patch(
            "app.application.analytics.bundle_tracking_service.BundleTrackingService",
        ) as tracking_cls:
            tracking = AsyncMock()
            tracking_cls.return_value = tracking
            result = await promo_service.redeem_code("BUNDLE-X", "s1")

        assert result is True
        tracking.track_event.assert_awaited_once()
        _, kwargs = tracking.track_event.await_args
        assert kwargs["event"] == "promo_applied"
        assert kwargs["promo_code"] == "BUNDLE-X"
