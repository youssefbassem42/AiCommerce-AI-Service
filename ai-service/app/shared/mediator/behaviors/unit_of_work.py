import logging
from typing import Any

from app.infrastructure.mongodb.uow import MongoUnitOfWork
from app.shared.mediator.pipeline import NextHandler, PipelineBehavior

logger = logging.getLogger(__name__)


class UnitOfWorkBehavior(PipelineBehavior):
    order: int = 1000

    async def handle(self, request: Any, next_handler: NextHandler) -> Any:
        async with MongoUnitOfWork():
            return await next_handler()
