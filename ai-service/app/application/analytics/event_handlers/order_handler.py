import logging

from app.application.analytics.bundle_tracking_service import BundleTrackingService
from app.domain.commerce.events.order_events import OrderCancelled, OrderPlaced
from app.shared.events.event_handler import IEventHandler

logger = logging.getLogger(__name__)


class OrderPlacedHandler(IEventHandler[OrderPlaced]):
    async def handle(self, event: OrderPlaced) -> None:
        logger.info(
            "Order placed: id=%s store=%s customer=%s total=%.2f, triggering dashboard insight recalculation",
            event.order_id,
            event.store_id,
            event.customer_id,
            event.total,
        )
        try:
            await BundleTrackingService().track_event(
                store_id=event.store_id,
                event="purchase_completed",
                customer_id=event.customer_id,
                metadata={"order_id": event.order_id, "total": event.total},
            )
        except Exception as exc:
            logger.warning("Failed to record purchase_completed for store %s: %s", event.store_id, exc)


class OrderCancelledHandler(IEventHandler[OrderCancelled]):
    async def handle(self, event: OrderCancelled) -> None:
        logger.info(
            "Order cancelled: id=%s store=%s, updating analytics metrics",
            event.order_id,
            event.store_id,
        )
