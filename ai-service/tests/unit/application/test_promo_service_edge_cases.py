from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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


class TestPromoCodeEdgeCases:
    async def test_find_existing_code_expired(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-EXPIRED": {
                    "discount_pct": 10.0,
                    "product_ids": ["p1", "p2"],
                    "used": False,
                    "expires_at": "2020-01-01T00:00:00",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1", "p2"], 10.0)
            assert code is None

    async def test_find_existing_code_already_used(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-USED": {
                    "discount_pct": 10.0,
                    "product_ids": ["p1", "p2"],
                    "used": True,
                    "expires_at": "2099-01-01T00:00:00",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1", "p2"], 10.0)
            assert code is None

    async def test_find_existing_code_wrong_discount(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-DIFF": {
                    "discount_pct": 5.0,
                    "product_ids": ["p1", "p2"],
                    "used": False,
                    "expires_at": "2099-01-01T00:00:00",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1", "p2"], 10.0)
            assert code is None

    async def test_find_existing_code_wrong_product_ids(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-MISMATCH": {
                    "discount_pct": 10.0,
                    "product_ids": ["p3", "p4"],
                    "used": False,
                    "expires_at": "2099-01-01T00:00:00",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1", "p2"], 10.0)
            assert code is None

    async def test_find_existing_code_missing_fields(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-INVALID": {
                    "discount_pct": 10.0,
                }
            }
        }
        code = await promo_service.find_existing_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_find_existing_code_invalid_expiry_format(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-BAD-DATE": {
                    "discount_pct": 10.0,
                    "product_ids": ["p1"],
                    "used": False,
                    "expires_at": "not-a-date",
                }
            }
        }
        with patch("app.application.recommendation.promo_service.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
            code = await promo_service.find_existing_code("s1", ["p1"], 10.0)
            assert code is None

    async def test_find_existing_code_info_as_list(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = {
            "promo_codes": {
                "BUNDLE-LIST": ["not_a_dict", 123],
            }
        }
        code = await promo_service.find_existing_code("s1", ["p1"], 10.0)
        assert code is None

    async def test_generate_code_when_product_not_found(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = None
        mock_collection.update_one = AsyncMock()
        mock_collection.update_one.return_value.modified_count = 0
        code = await promo_service.generate_code("s1", ["nonexistent"], 10.0)
        assert code.startswith("BUNDLE-")

    async def test_redeem_nonexistent_code(self, promo_service, mock_collection):
        mock_collection.update_one.return_value.modified_count = 0
        result = await promo_service.redeem_code("BUNDLE-NONEXISTENT", "s1")
        assert result is False

    async def test_generate_with_empty_product_list(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = None
        code = await promo_service.generate_code("s1", [], 10.0)
        assert code.startswith("BUNDLE-")

    async def test_generate_with_zero_discount(self, promo_service, mock_collection):
        mock_collection.find_one.return_value = None
        mock_collection.update_one = AsyncMock()
        code = await promo_service.generate_code("s1", ["p1"], 0.0)
        assert code.startswith("BUNDLE-")
