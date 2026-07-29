import logging

from app.domain.commerce.events.order_events import OrderPlaced, OrderCancelled
from app.shared.events.event_handler import IEventHandler

logger = logging.getLogger(__name__)


class OrderPlacedHandler(IEventHandler[OrderPlaced]):
    async def handle(self, event: OrderPlaced) -> None:
        logger.info(
            "Order placed: id=%s store=%s customer=%s total=%.2f, "
            "triggering dashboard insight recalculation",
            event.order_id,
            event.store_id,
            event.customer_id,
            event.total,
        )


class OrderCancelledHandler(IEventHandler[OrderCancelled]):
    async def handle(self, event: OrderCancelled) -> None:
        logger.info(
            "Order cancelled: id=%s store=%s, updating analytics metrics",
            event.order_id,
            event.store_id,
        )
