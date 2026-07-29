import os
from pydantic_settings import BaseSettings


class MongoSettings(BaseSettings):
    """Mongo database settings using pydantic-settings."""
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB: str = os.getenv("MONGO_DB", "ai_commerce")


