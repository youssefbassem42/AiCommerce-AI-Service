import os
from pydantic_settings import BaseSettings


class QdrantSettings(BaseSettings):
    """Qdrant vector database settings using pydantic-settings."""
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
