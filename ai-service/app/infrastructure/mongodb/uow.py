from contextlib import asynccontextmanager
from typing import AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorClientSession
from app.infrastructure.mongodb.client import MongoClientManager
import logging

logger = logging.getLogger(__name__)

class MongoUnitOfWork:
    """
    Manages MongoDB client sessions and transactions (Unit of Work).
    Allows executing multiple repository operations atomically.
    """

    def __init__(self):
        # Retrieve the underlying MongoClient from the db manager
        self._db = MongoClientManager.get_database()
        self._client: AsyncIOMotorClient = self._db.client
        self.session: AsyncIOMotorClientSession | None = None

    async def __aenter__(self) -> "MongoUnitOfWork":
        """Start a new session and begin a transaction."""
        self.session = await self._client.start_session()
        self.session.start_transaction()
        logger.debug("MongoDB transaction started.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit or abort the transaction on exit based on exceptions."""
        if self.session:
            try:
                if exc_type is not None:
                    logger.warning(f"Aborting MongoDB transaction due to exception: {str(exc_val)}")
                    await self.session.abort_transaction()
                else:
                    logger.debug("Committing MongoDB transaction...")
                    await self.session.commit_transaction()
            except Exception as e:
                logger.error(f"Error handling transaction exit: {str(e)}")
                raise e
            finally:
                await self.session.end_session()
                self.session = None
                logger.debug("MongoDB session closed.")

    async def commit(self) -> None:
        """Manually commit the active transaction."""
        if self.session and self.session.in_transaction:
            await self.session.commit_transaction()
            logger.info("MongoDB transaction manually committed.")

    async def rollback(self) -> None:
        """Manually abort/rollback the active transaction."""
        if self.session and self.session.in_transaction:
            await self.session.abort_transaction()
            logger.info("MongoDB transaction manually rolled back.")


@asynccontextmanager
async def get_unit_of_work() -> AsyncGenerator[MongoUnitOfWork, None]:
    async with MongoUnitOfWork() as uow:
        yield uow
