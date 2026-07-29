import os
from pydantic_settings import BaseSettings


class RedisSettings(BaseSettings):
    """Qdrant settings using pydantic-settings."""
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
