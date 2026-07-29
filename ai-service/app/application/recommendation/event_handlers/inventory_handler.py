import logging

from app.domain.commerce.events.inventory_events import InventoryChanged
from app.shared.events.event_handler import IEventHandler

logger = logging.getLogger(__name__)


class InventoryChangedHandler(IEventHandler[InventoryChanged]):
    async def handle(self, event: InventoryChanged) -> None:
        logger.info(
            "Inventory changed for product=%s variant=%s old=%d new=%d, "
            "triggering recommendation recalculation",
            event.product_id,
            event.variant_id,
            event.old_quantity,
            event.new_quantity,
        )
