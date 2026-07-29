from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoClientManager:
    """Manages the lifecycle of the AsyncIOMotorClient with pooling and connection checks."""
    _client: AsyncIOMotorClient | None = None
    _db = None

    @classmethod
    async def connect(cls) -> None:
        """Establish the database connection and verify it immediately via ping."""
        if not cls._client:
            logger.info("Initializing AsyncIOMotorClient...")
            try:
                cls._client = AsyncIOMotorClient(
                    settings.MONGO_SETTINGS.MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=10000,
                    retryWrites=True,
                    retryReads=True,
                    maxPoolSize=100,
                    minPoolSize=10
                )
                cls._db = cls._client[settings.MONGO_SETTINGS.MONGO_DB]
                # Force validation check
                await cls._client.admin.command("ping")
                logger.info("Successfully connected and pinged MongoDB database.")
            except Exception as e:
                logger.critical(f"Failed to connect to MongoDB: {str(e)}")
                cls._client = None
                cls._db = None
                raise e

    @classmethod
    def disconnect(cls) -> None:
        """Close the database connection."""
        if cls._client:
            logger.info("Closing MongoDB connection...")
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("MongoDB connection closed.")

    @classmethod
    def get_database(cls):
        """Retrieve the database instance (falls back to lazy sync connection if not initialized)."""
        if cls._db is None:
            logger.warning("Database requested before async connect() was executed. Initializing lazily.")
            cls._client = AsyncIOMotorClient(
                settings.MONGO_SETTINGS.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=10000,
                retryWrites=True,
                retryReads=True,
                maxPoolSize=100,
                minPoolSize=10
            )
            cls._db = cls._client[settings.MONGO_SETTINGS.MONGO_DB]
        return cls._db

def get_mongodb():
    """Retrieve the database reference."""
    return MongoClientManager.get_database()
