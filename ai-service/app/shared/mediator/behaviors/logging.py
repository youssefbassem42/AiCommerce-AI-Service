import logging
import time
from typing import Any

from app.shared.mediator.pipeline import PipelineBehavior, NextHandler

logger = logging.getLogger(__name__)


class LoggingBehavior(PipelineBehavior):
    order: int = 0

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        request_name = type(request).__name__
        logger.info("Handling %s: %s", request_name, request)
        start = time.monotonic()
        try:
            result = await next_handler()
            elapsed = time.monotonic() - start
            logger.info("%s completed in %.3fms", request_name, elapsed * 1000)
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("%s failed after %.3fms: %s", request_name, elapsed * 1000, str(e))
            raise
