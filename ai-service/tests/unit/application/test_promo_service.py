from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.recommendation.promo_service import PromoCodeService


@pytest.fixture
def mock_collection():
    return AsyncMock()


@pytest.fixture
def promo_service(mock_collection):
    with patch("app.application.recommendation.promo_service.get_products_collection", return_value=mock_collection):
        service = PromoCodeService()
        service._products_collection = mock_collection
        yield service


class TestPromoCodeService:
    async def test_find_existing_code_returns_none(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = None
        code = await promo_service.find_existing_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_find_existing_code_finds_match(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-ABC123": {
                    "discount_pct": 10.0,
                    "product_ids": ["p1", "p2"],
                    "used": False,
                    "expires_at": "2099-01-01T00:00:00",
                }
            }
        }
        from datetime import UTC, datetime
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1", "p2"], 10.0)
            assert code == "BUNDLE-ABC123"

    async def test_generate_code_reuses_existing(self, promo_service, mock_collection):
        from datetime import UTC, datetime
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-EXISTING": {
                    "discount_pct": 10.0,
                    "product_ids": ["p1", "p2"],
                    "used": False,
                    "expires_at": "2099-01-01T00:00:00",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.generate_code("s1", ["p1", "p2"], 10.0)
            assert code == "BUNDLE-EXISTING"

    async def test_generate_code_creates_new(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = None
        mock_collection.update_one = AsyncMock()
        mock_collection.update_one.return_value.modified_count = 1

        code = await promo_service.generate_code("s1", ["p1", "p2"], 15.0)
        assert code.startswith("BUNDLE-")
        assert mock_collection.update_one.await_count == 2  # one per product

    async def test_redeem_code(self, promo_service, mock_collection):
        mock_collection.update_one.return_value.modified_count = 1
        result = await promo_service.redeem_code("BUNDLE-TEST", "s1")
        assert result is True
