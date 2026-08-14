"""Fix 5.6: widget chat emits bundle_shown / promo_displayed analytics events."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.api.widget.router import _track_bundle_events


def test_bundle_shown_recorded_without_promo():
    tracker = MagicMock()
    tracker.track_event = AsyncMock(return_value={"recorded": True})
    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        import asyncio

        asyncio.run(
            _track_bundle_events(
                store_id="s1",
                bundle={"items": [{"product_id": "p1"}, {"product_id": "p2"}], "promo_code": None},
                conversation_id="conv-1",
                customer_id="c1",
            )
        )

    assert tracker.track_event.await_count == 1
    kwargs = tracker.track_event.await_args.kwargs
    assert kwargs["event"] == "bundle_shown"
    assert kwargs["store_id"] == "s1"
    assert kwargs["product_ids"] == ["p1", "p2"]
    assert kwargs["conversation_id"] == "conv-1"
    assert kwargs["customer_id"] == "c1"


def test_promo_displayed_recorded_alongside_shown():
    tracker = MagicMock()
    tracker.track_event = AsyncMock(return_value={"recorded": True})
    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        import asyncio

        asyncio.run(
            _track_bundle_events(
                store_id="s1",
                bundle={"items": [{"product_id": "p1"}], "promo_code": "BUNDLE-X"},
            )
        )

    events = [call.kwargs["event"] for call in tracker.track_event.await_args_list]
    assert events == ["bundle_shown", "promo_displayed"]
    assert tracker.track_event.await_args.kwargs["promo_code"] == "BUNDLE-X"


def test_no_bundle_no_events():
    tracker = MagicMock()
    tracker.track_event = AsyncMock()
    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        import asyncio

        asyncio.run(_track_bundle_events(store_id="s1", bundle=None))

    tracker.track_event.assert_not_awaited()


def test_tracking_failure_is_swallowed():
    tracker = MagicMock()
    tracker.track_event = AsyncMock(side_effect=RuntimeError("db down"))
    with patch("app.api.widget.router.BundleTrackingService", return_value=tracker):
        import asyncio

        asyncio.run(
            _track_bundle_events(
                store_id="s1",
                bundle={"items": [{"product_id": "p1"}], "promo_code": None},
            )
        )
