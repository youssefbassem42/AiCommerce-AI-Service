from typing import Any
import logging

from app.shared.mediator.pipeline import PipelineBehavior, NextHandler
from app.infrastructure.mongodb.uow import MongoUnitOfWork

logger = logging.getLogger(__name__)


class UnitOfWorkBehavior(PipelineBehavior):
    order: int = 1000

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        async with MongoUnitOfWork() as uow:
            return await next_handler()
