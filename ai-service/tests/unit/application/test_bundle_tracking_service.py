from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.analytics.bundle_tracking_service import (
    DEFAULT_THRESHOLD,
    BundleTrackingService,
    _make_bundle_key,
)


def _make_find_cursor(data: list) -> MagicMock:
    cursor = MagicMock()
    cursor.__aiter__.return_value = iter(data)
    return cursor


@pytest.fixture
def mock_tracking():
    col = MagicMock()
    col.find_one_and_update = AsyncMock()
    col.find_one = AsyncMock()
    col.update_one = AsyncMock()
    col.find = MagicMock()
    col.find.return_value.sort.return_value = _make_find_cursor([])
    return col


@pytest.fixture
def mock_events():
    col = MagicMock()
    col.insert_one = AsyncMock()
    return col


@pytest.fixture
def mock_insights():
    col = MagicMock()
    col.find_one = AsyncMock()
    col.update_one = AsyncMock()
    col.replace_one = AsyncMock()
    return col


@pytest.fixture
def service(mock_tracking, mock_events, mock_insights):
    with (
        patch(
            "app.application.analytics.bundle_tracking_service.get_bundle_tracking_collection",
            return_value=mock_tracking,
        ),
        patch(
            "app.application.analytics.bundle_tracking_service.get_bundle_events_collection",
            return_value=mock_events,
        ),
        patch(
            "app.application.analytics.bundle_tracking_service.get_dashboard_insights_collection",
            return_value=mock_insights,
        ),
    ):
        svc = BundleTrackingService()
        svc._tracking_collection = mock_tracking
        svc._events_collection = mock_events
        svc._insights_collection = mock_insights
        yield svc


class TestBundleKey:
    def test_make_bundle_key_is_deterministic(self):
        k1 = _make_bundle_key(["p1", "p2"], 10.0)
        k2 = _make_bundle_key(["p1", "p2"], 10.0)
        assert k1 == k2

    def test_make_bundle_key_order_independent(self):
        k1 = _make_bundle_key(["p1", "p2"], 10.0)
        k2 = _make_bundle_key(["p2", "p1"], 10.0)
        assert k1 == k2

    def test_make_bundle_key_different_discount(self):
        k1 = _make_bundle_key(["p1", "p2"], 10.0)
        k2 = _make_bundle_key(["p1", "p2"], 15.0)
        assert k1 != k2


class TestBundleTrackingService:
    async def test_track_event_records_and_mirrors_counter(self, service, mock_events, mock_tracking):
        mock_tracking.update_one.return_value.modified_count = 1

        result = await service.track_event(
            store_id="s1",
            event="bundle_clicked",
            customer_id="c1",
            conversation_id="conv1",
            product_ids=["p1", "p2"],
            discount_pct=10.0,
        )

        assert result["recorded"] is True
        assert result["event"] == "bundle_clicked"
        mock_events.insert_one.assert_awaited_once()
        doc = mock_events.insert_one.await_args.args[0]
        assert doc["store_id"] == "s1"
        assert doc["event"] == "bundle_clicked"
        assert doc["customer_id"] == "c1"
        assert doc["product_ids"] == ["p1", "p2"]
        mock_tracking.update_one.assert_awaited_once()
        update_filter = mock_tracking.update_one.await_args.args[0]
        update = mock_tracking.update_one.await_args.args[1]
        assert update_filter == {"store_id": "s1", "bundle_key": doc["bundle_key"]}
        assert update["$inc"] == {"click_count": 1}

    async def test_track_event_promo_copied(self, service, mock_events, mock_tracking):
        result = await service.track_event(
            store_id="s1",
            event="promo_copied",
            promo_code="BUNDLE-X",
            product_ids=["p1"],
            discount_pct=15.0,
        )
        assert result["recorded"] is True
        doc = mock_events.insert_one.await_args.args[0]
        assert doc["promo_code"] == "BUNDLE-X"
        assert mock_tracking.update_one.await_args.args[1]["$inc"] == {"copy_count": 1}

    async def test_track_event_purchase_completed(self, service, mock_events, mock_tracking):
        result = await service.track_event(
            store_id="s1",
            event="purchase_completed",
            customer_id="c1",
            metadata={"order_id": "ord_1"},
        )
        assert result["recorded"] is True
        doc = mock_events.insert_one.await_args.args[0]
        assert doc["metadata"] == {"order_id": "ord_1"}
        assert mock_tracking.update_one.await_args.args[1]["$inc"] == {"purchase_count": 1}

    async def test_track_event_unknown_event_ignored(self, service, mock_events, mock_tracking):
        result = await service.track_event(store_id="s1", event="not_a_real_event")
        assert result["recorded"] is False
        mock_events.insert_one.assert_not_awaited()
        mock_tracking.update_one.assert_not_awaited()

    async def test_track_event_deterministic_bundle_key(self, service, mock_events, mock_tracking):
        await service.track_event(store_id="s1", event="bundle_shown", product_ids=["p2", "p1"], discount_pct=10.0)
        await service.track_event(store_id="s1", event="bundle_shown", product_ids=["p1", "p2"], discount_pct=10.0)
        docs = [c.args[0] for c in mock_events.insert_one.await_args_list]
        assert docs[0]["bundle_key"] == docs[1]["bundle_key"]

    async def test_track_copy_event_first_time(self, service, mock_tracking, mock_insights):
        mock_tracking.find_one_and_update.return_value = {
            "_id": "doc_id",
            "copy_count": 1,
            "is_top": False,
            "store_id": "s1",
            "bundle_key": "test_key",
        }
        mock_insights.find_one.return_value = None

        result = await service.track_copy_event(
            store_id="s1",
            promo_code="BUNDLE-TEST",
            product_ids=["p1", "p2"],
            discount_pct=10.0,
            total_discount=50.0,
            total_original=500.0,
        )

        assert result["copy_count"] == 1
        assert result["is_top"] is False
        assert result["threshold"] == DEFAULT_THRESHOLD
        mock_tracking.find_one_and_update.assert_awaited_once()

    async def test_track_copy_event_promotes_on_threshold(self, service, mock_tracking, mock_insights):
        mock_tracking.find_one_and_update.return_value = {
            "_id": "doc_id",
            "copy_count": 5,
            "is_top": False,
            "promoted_at": None,
        }
        mock_insights.find_one.return_value = {"metadata": {"tracking_config": {"threshold": 5, "enabled": True}}}

        result = await service.track_copy_event(
            store_id="s1",
            promo_code="BUNDLE-TEST",
            product_ids=["p1", "p2"],
            discount_pct=10.0,
            total_discount=50.0,
            total_original=500.0,
        )

        assert result["copy_count"] == 5
        assert result["is_top"] is True
        mock_tracking.update_one.assert_awaited_once()

    async def test_get_tracked_bundles(self, service, mock_tracking):
        now = datetime.now(UTC)
        mock_tracking.find.return_value.sort.return_value = _make_find_cursor(
            [
                {
                    "_id": "doc1",
                    "store_id": "s1",
                    "bundle_key": "key1",
                    "product_ids": ["p1", "p2"],
                    "discount_pct": 10.0,
                    "total_original": 500.0,
                    "total_discount": 50.0,
                    "promo_code": "B1",
                    "copy_count": 5,
                    "is_top": True,
                    "first_copied_at": now,
                    "last_copied_at": now,
                    "promoted_at": now,
                },
            ]
        )

        bundles = await service.get_tracked_bundles("s1")

        assert len(bundles) == 1
        assert bundles[0]["bundle_key"] == "key1"
        assert bundles[0]["id"] == "doc1"

    async def test_get_tracked_bundles_top_only(self, service, mock_tracking):
        mock_tracking.find.return_value.sort.return_value = _make_find_cursor(
            [
                {
                    "_id": "doc1",
                    "store_id": "s1",
                    "bundle_key": "top1",
                    "product_ids": ["p1"],
                    "discount_pct": 10.0,
                    "total_original": 100.0,
                    "total_discount": 10.0,
                    "promo_code": "B1",
                    "copy_count": 5,
                    "is_top": True,
                },
            ]
        )

        bundles = await service.get_tracked_bundles("s1", is_top_only=True)

        assert len(bundles) == 1
        mock_tracking.find.assert_called_once_with({"store_id": "s1", "is_top": True})

    async def test_get_tracked_bundle_found(self, service, mock_tracking):
        mock_tracking.find_one.return_value = {
            "_id": "doc1",
            "store_id": "s1",
            "bundle_key": "key1",
            "product_ids": ["p1"],
            "discount_pct": 5.0,
            "total_original": 200.0,
            "total_discount": 10.0,
            "promo_code": "B1",
            "copy_count": 3,
            "is_top": False,
        }

        result = await service.get_tracked_bundle("s1", "key1")

        assert result is not None
        assert result["id"] == "doc1"
        assert result["bundle_key"] == "key1"

    async def test_get_tracked_bundle_not_found(self, service, mock_tracking):
        mock_tracking.find_one.return_value = None

        result = await service.get_tracked_bundle("s1", "nonexistent")

        assert result is None

    async def test_promote_bundle(self, service, mock_tracking, mock_insights):
        mock_tracking.update_one.return_value.modified_count = 1
        mock_insights.find_one.return_value = {"metadata": {"tracking_config": {"threshold": 5, "enabled": True}}}

        result = await service.promote_bundle("s1", "key1")

        assert result is True
        mock_tracking.update_one.assert_awaited_once()

    async def test_promote_bundle_not_found(self, service, mock_tracking):
        mock_tracking.update_one.return_value.modified_count = 0

        result = await service.promote_bundle("s1", "nonexistent")

        assert result is False

    async def test_demote_bundle(self, service, mock_tracking, mock_insights):
        mock_tracking.update_one.return_value.modified_count = 1
        mock_insights.find_one.return_value = {"metadata": {"tracking_config": {"threshold": 5, "enabled": True}}}

        result = await service.demote_bundle("s1", "key1")

        assert result is True

    async def test_get_config_default(self, service, mock_insights):
        mock_insights.find_one.return_value = None

        config = await service.get_config("s1")

        assert config["threshold"] == DEFAULT_THRESHOLD
        assert config["enabled"] is True

    async def test_get_config_custom(self, service, mock_insights):
        mock_insights.find_one.return_value = {
            "metadata": {
                "tracking_config": {"threshold": 10, "enabled": True},
            }
        }

        config = await service.get_config("s1")

        assert config["threshold"] == 10
        assert config["enabled"] is True

    async def test_update_config(self, service, mock_insights):
        mock_insights.find_one.return_value = {
            "metadata": {
                "tracking_config": {"threshold": 5, "enabled": True},
            }
        }

        config = await service.update_config(store_id="s1", threshold=8)

        assert config["threshold"] == 8
        mock_insights.update_one.assert_awaited_once()
